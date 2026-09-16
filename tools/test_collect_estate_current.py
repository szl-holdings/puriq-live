"""Offline audit-collector boundaries; no acquired repository code executes."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import collect_estate_current as c

class CollectorTests(unittest.TestCase):
    def archive(self, rows):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for name,body in rows:
                z.writestr(name,body)
        return stream.getvalue()

    def test_allowlist(self):
        for url in ('https://api.github.com/repos/szl-holdings/a11oy',
                    'https://huggingface.co/api/models?author=SZLHOLDINGS',
                    'https://szlholdings-finance.hf.space/',
                    'https://szlholdings-readme.static.hf.space/'):
            with self.subTest(url=url): self.assertTrue(c.allowed(url))
        for url in ('http://api.github.com/', 'https://evil.hf.space/',
                    'https://szlholdings-x.hf.space.evil.example/',
                    'https://api.github.com:444/', 'https://user@api.github.com/',
                    'https://api.github.com/#x', 'https://api.github.com:bad/',
                    'https://127.0.0.1/', 'https://szlholdings-.hf.space/'):
            with self.subTest(url=url): self.assertFalse(c.allowed(url))

    def test_paths(self):
        self.assertEqual(str(c.member_path('root/src/app.py')),'src/app.py')
        for path in ('/root/x.py','root/../x.py','root/a\\b.py','root/C:x.py',
                     'root/./x.py','root//x.py','root/../root/x.py'):
            with self.subTest(path=path), self.assertRaises(ValueError): c.member_path(path)

    def test_acquisition_matches_exact_blob_and_never_executes(self):
        raw=b'raise RuntimeError("must not execute")\n'
        with tempfile.TemporaryDirectory() as d:
            result=c.acquire_zip(self.archive([('root/a.py',raw)]),
                {'a.py':{'sha':c.blob_sha(raw),'mode':'100644'}},Path(d))
            self.assertEqual(result['text_files_acquired'],1)
            self.assertFalse(result['code_executed'])
            self.assertEqual((Path(d)/'a.py').read_bytes(),raw)
            self.assertEqual(result['files'][0]['syntax']['state'],'PARSED')

    def test_mismatched_blob_rejected(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaisesRegex(ValueError,'tree/blob'):
            c.acquire_zip(self.archive([('root/a.py',b'x=1')]),{'a.py':{'sha':'0'*40}},Path(d))

    def test_missing_archive_file_is_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            out=c.acquire_zip(self.archive([]),{'a.py':{'sha':'1'*40}},Path(d))
            self.assertEqual(out['files'][0]['reason'],'NOT_IN_ARCHIVE')

    def test_unlisted_member_not_written(self):
        with tempfile.TemporaryDirectory() as d:
            out=c.acquire_zip(self.archive([('root/a.py',b'x=1')]),{},Path(d))
            self.assertEqual(out['files'][0]['reason'],'NOT_IN_OBSERVED_TREE')
            self.assertFalse((Path(d)/'a.py').exists())

    def test_symlink_not_written(self):
        with tempfile.TemporaryDirectory() as d:
            raw=b'../../outside'
            out=c.acquire_zip(self.archive([('root/a.py',raw)]),{'a.py':{'mode':'120000','sha':c.blob_sha(raw)}},Path(d))
            self.assertEqual(out['files'][0]['reason'],'SYMLINK')
            self.assertFalse((Path(d)/'a.py').exists())

    def test_file_byte_bound(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c,'MAX_FILE',2):
            out=c.acquire_zip(self.archive([('root/a.py',b'xyz')]),{'a.py':{'sha':'1'*40}},Path(d))
            self.assertEqual(out['files'][0]['reason'],'FILE_BYTE_LIMIT')

    def test_total_expanded_bound(self):
        raw=b'x=1'
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c,'MAX_EXPANDED',2), self.assertRaisesRegex(ValueError,'expanded'):
            c.acquire_zip(self.archive([('root/a.py',raw)]),{'a.py':{'sha':c.blob_sha(raw)}},Path(d))

    def test_non_text_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            out=c.acquire_zip(self.archive([('root/a.bin',b'xyz')]),{'a.bin':{'sha':'1'*40}},Path(d))
            self.assertEqual(out['files'][0]['reason'],'NON_TEXT_POLICY')

    def test_non_utf8_recorded(self):
        raw=b'\xff'
        with tempfile.TemporaryDirectory() as d:
            out=c.acquire_zip(self.archive([('root/a.py',raw)]),{'a.py':{'sha':c.blob_sha(raw)}},Path(d))
            self.assertEqual(out['files'][0]['reason'],'NON_UTF8')

    def test_syntax_is_observation_not_semantic_review(self):
        self.assertEqual(c.syntax('x.py',b'def :')['state'],'PARSE_EXCEPTION')
        self.assertEqual(c.syntax('x.json',b'{')['state'],'PARSE_EXCEPTION')
        self.assertEqual(c.syntax('x.toml',b'[a')['state'],'PARSE_EXCEPTION')
        self.assertEqual(c.syntax('x.js',b'bad javascript')['state'],'NOT_EVALUATED')
        self.assertFalse(c.syntax('x.py',b'import os')['semantic_review'])

    def test_pagination_complete(self):
        first='https://huggingface.co/api/models?author=SZLHOLDINGS'
        second=first+'&cursor=next'
        with mock.patch.object(c,'get',side_effect=[(b'[1]',{'Link':f'<{second}>; rel="next"'}),(b'[2]',{})]):
            self.assertEqual(c.paged(first),[1,2])

    def test_pagination_cycle_and_origin_fail(self):
        url='https://huggingface.co/api/models?author=SZLHOLDINGS'
        for next_url in (url,'https://api.github.com/repos'):
            with self.subTest(next_url=next_url), mock.patch.object(c,'get',return_value=(b'[]',{'Link':f'<{next_url}>; rel="next"'})), self.assertRaisesRegex(ValueError,'pagination'):
                c.paged(url)

    def test_pagination_schema_fail(self):
        with mock.patch.object(c,'get',return_value=(b'{}',{})), self.assertRaises(ValueError):
            c.paged('https://huggingface.co/api/models')

    def test_private_repository_rejected_before_read(self):
        with mock.patch.object(c,'json_get') as get, self.assertRaises(ValueError):
            c.inspect_repo({'full_name':'szl-holdings/private','private':True})
        get.assert_not_called()

    def test_output_directory_cannot_mix_old_receipts(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(c,'OUT',Path(d)), self.assertRaises(SystemExit):
            c.main()

    def test_redirect_is_rejected_and_closed_without_body_read(self):
        body=mock.Mock()
        body.read.side_effect=AssertionError('unbounded body read')
        with self.assertRaises(ValueError):
            c.Redirect().http_error_302(None,body,302,'found',{'Location':'https://huggingface.co/x'})
        body.close.assert_called_once()
        body.read.assert_not_called()

    def test_get_has_byte_limits_and_only_origin_auth(self):
        class Response:
            headers={'Content-Length':'2'}
            def __init__(self): self.stream=io.BytesIO(b'{}')
            def read(self,n): return self.stream.read(n)
            def __enter__(self): return self
            def __exit__(self,*a): pass
        seen=[]
        def open_(req,timeout): seen.append(req); return Response()
        with mock.patch.object(c,'build_opener',return_value=mock.Mock(open=open_)), mock.patch.dict(c.os.environ,{'GITHUB_TOKEN':'inert-fixture-token'}):
            self.assertEqual(c.get('https://api.github.com/repos/x/y')[0],b'{}')
            self.assertEqual(c.get('https://huggingface.co/api/models')[0],b'{}')
            with self.assertRaises(ValueError): c.get('https://api.github.com/repos/x/y',1)
        self.assertEqual(seen[0].get_header('Authorization'),'Bearer inert-fixture-token')
        self.assertIsNone(seen[1].get_header('Authorization'))

if __name__=='__main__': unittest.main()
