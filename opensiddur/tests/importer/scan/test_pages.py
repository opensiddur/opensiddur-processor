"""Cache isolation, download failure handling and image bands on tiny fixtures."""
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PIL import Image

from opensiddur.importer.scan import pages as p


class PageTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.profile=p.BookProfile('fixture','fixture-item',self.root/'source',self.root/'cache',self.root/'map.json')
        self.payload={'identifier':'fixture-item','pages':[
            {'scan_page':1,'ia_leaf':0,'printed_page':'x','side':'he','facs':'scan'},
            {'scan_page':2,'ia_leaf':1,'printed_page':None,'facs':'scan2'}]}
        self.write_map()

    def write_map(self):
        self.profile.page_map.write_text(json.dumps(self.payload))

    def image(self):
        data=io.BytesIO();Image.new('RGB',(8,20),'white').save(data,format='JPEG');return data.getvalue()

    def response(self,data):
        response=Mock();response.iter_content.return_value=[data[:10],data[10:]];return response

    def test_identity_lookup_legacy_cache_and_explicit_unknown_profile(self):
        refs=p.load_pages(self.profile)
        self.assertEqual(refs['s1'].language,'he')
        self.assertEqual(p.lookup(self.profile,'x'),refs['s1'])
        self.assertEqual(p.cache_designation(self.profile,refs['s1']),'s1')
        legacy=p.BookProfile('legacy','fixture-item',self.root,self.root,self.profile.page_map,True)
        self.assertEqual(p.cache_designation(legacy,refs['s1']),'x')
        self.assertEqual(p.cache_designation(legacy,refs['s2']),'s2')
        with self.assertRaises(p.ScanError):p.BookProfile.for_book('unknown',self.root,self.root)
        for entry in [dict(self.payload['pages'][0],scan_page=3),dict(self.payload['pages'][0])]:
            self.payload['pages'].append(entry);self.write_map()
            with self.assertRaisesRegex(p.ScanError,'Invalid or duplicate'):p.load_pages(self.profile)
            self.payload['pages'].pop()

    def test_fetch_verifies_download_and_reuses_cache_unless_forced(self):
        archive=Mock();response=self.response(self.image())
        with patch.object(p,'http_get',return_value=response)as get:
            destination=p.fetch(self.profile,'s1',archive=archive)
            self.assertTrue(destination.is_file());response.close.assert_called_once()
            self.assertFalse(destination.with_suffix('.jpg.part').exists())
            p.fetch(self.profile,'s1',archive=archive);get.assert_called_once()
            p.fetch(self.profile,'s1',archive=archive,force=True);self.assertEqual(get.call_count,2)
            self.assertIn('fixture-item',get.call_args.args[1])

    def test_failed_download_preserves_previous_cache_and_cleans_partial(self):
        destination=self.profile.cache_directory/'pages/s1.jpg';destination.parent.mkdir(parents=True);destination.write_bytes(self.image())
        old=destination.read_bytes();response=self.response(b'not an image')
        with patch.object(p,'http_get',return_value=response),self.assertRaises(OSError):
            p.fetch(self.profile,'s1',archive=Mock(),force=True)
        self.assertEqual(destination.read_bytes(),old)
        self.assertFalse(destination.with_suffix('.jpg.part').exists());response.close.assert_called_once()
        response=self.response(self.image());response.iter_content.side_effect=OSError('network interrupted')
        with patch.object(p,'http_get',return_value=response),self.assertRaises(OSError):
            p.fetch(self.profile,'s1',archive=Mock(),force=True)
        self.assertEqual(destination.read_bytes(),old);self.assertFalse(destination.with_suffix('.jpg.part').exists())

    def test_contact_required_only_for_uncached_network_request(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(p.ScanError,'CONTACT_EMAIL'):
            p.fetch(self.profile,'s1')
        for kwargs,env in [({'contact_email':'contact@example.org'},{}),({}, {'OPENSIDDUR_CONTACT_EMAIL':'contact@example.org'})]:
            with self.subTest(kwargs=kwargs),patch.dict(os.environ,env,clear=True),patch.object(p,'connect',return_value=Mock())as connect,patch.object(p,'resolve_agent_model',return_value='fixture-model'),patch.object(p,'http_get',return_value=self.response(self.image())):
                p.fetch(self.profile,'s1',force=True,**kwargs)
                connect.assert_called_once_with('contact@example.org',model='fixture-model')

    def test_bands_overlap_and_enlarge_with_profile_cache_path(self):
        source=self.profile.cache_directory/'pages/s1.jpg';source.parent.mkdir(parents=True);source.write_bytes(self.image())
        destinations=p.bands(self.profile,'s1',count=2,overlap=.1,scale=2)
        sizes=[]
        for path in destinations:
            with Image.open(path) as image:sizes.append(image.size)
        self.assertEqual(sizes,[(16,22),(16,22)])
        self.assertTrue(all(path.parent==self.profile.cache_directory/'bands'for path in destinations))
        for kwargs in [{'count':0},{'overlap':.5},{'overlap':-.1},{'scale':0}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):p.cut_bands(source,[],**kwargs)

    def test_cli_fetches_before_bands_and_can_skip_bands(self):
        for skip in [False,True]:
            with self.subTest(skip=skip),patch.object(p.BookProfile,'for_book',return_value=self.profile),patch.object(p,'fetch',return_value=Path('image.jpg'))as fetch,patch.object(p,'bands',return_value=[Path('band.png')])as bands,redirect_stdout(io.StringIO()):
                self.assertEqual(p.main(['s1','--book','fixture','--contact-email','contact@example.org']+(['--no-bands']if skip else [])),0)
                fetch.assert_called_once_with(self.profile,'s1',contact_email='contact@example.org')
                self.assertEqual(bands.call_count,0 if skip else 1)
