import io, tarfile, unittest
from unittest.mock import patch
import verify_public_reference_bundle as v

class ArchiveLimits(unittest.TestCase):
    def member(self,name='file',size=1,kind=tarfile.REGTYPE):
        m=tarfile.TarInfo(name);m.size=size;m.type=kind;return m
    def test_valid_boundaries(self):
        with patch.multiple(v,MAX_ARCHIVE_MEMBERS=2,MAX_MEMBER_BYTES=3,MAX_EXPANDED_BYTES=4):
            self.assertEqual(len(v.bounded_members([self.member('a',3),self.member('b',1)])),2)
    def test_member_count(self):
        with patch.object(v,'MAX_ARCHIVE_MEMBERS',1),self.assertRaisesRegex(ValueError,'count'):
            v.bounded_members([self.member('a'),self.member('b')])
    def test_member_size(self):
        with patch.object(v,'MAX_MEMBER_BYTES',2),self.assertRaisesRegex(ValueError,'member size'):
            v.bounded_members([self.member(size=3)])
    def test_expanded_size(self):
        with patch.object(v,'MAX_EXPANDED_BYTES',3),self.assertRaisesRegex(ValueError,'expanded size'):
            v.bounded_members([self.member('a',2),self.member('b',2)])
    def test_unsafe_and_duplicate(self):
        for entries in [[self.member('../bad')],[self.member('/bad')],[self.member('link',kind=tarfile.SYMTYPE)],[self.member('same'),self.member('same')]]:
            with self.subTest(entries=[x.name for x in entries]),self.assertRaises(ValueError):v.bounded_members(entries)
    def test_real_tar_headers_rejected_before_extraction(self):
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode='w') as archive:
            archive.addfile(self.member('a',2),io.BytesIO(b'ab'))
            archive.addfile(self.member('b',2),io.BytesIO(b'cd'))
        raw.seek(0)
        with tarfile.open(fileobj=raw) as archive,patch.object(v,'MAX_EXPANDED_BYTES',3),self.assertRaisesRegex(ValueError,'expanded size'):
            v.bounded_members(archive)
if __name__=='__main__':unittest.main()
