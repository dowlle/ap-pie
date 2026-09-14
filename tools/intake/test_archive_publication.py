import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from publish_beta_archives import INGEST


class ArchiveTransferTests(unittest.TestCase):
    def test_ingest_validates_paths_and_hash_before_installing_bytes(self):
        payload=b'archive fixture'
        digest=hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'cache'
            code=INGEST.replace("Path('/app/.state/discovery-archives')",'Path('+repr(str(root))+')')
            for name,success in [(digest+'.apworld',True),('../outside.apworld',False),('0'*64+'.apworld',False)]:
                body=io.BytesIO()
                with tarfile.open(fileobj=body,mode='w') as stream:
                    member=tarfile.TarInfo(name);member.size=len(payload)
                    stream.addfile(member,io.BytesIO(payload))
                result=subprocess.run([sys.executable,'-I','-c',code],input=body.getvalue(),capture_output=True)
                self.assertEqual(result.returncode==0,success)
            self.assertEqual((root/(digest+'.apworld')).read_bytes(),payload)
            self.assertEqual(len(list(root.iterdir())),1)


if __name__ == '__main__':
    unittest.main()
