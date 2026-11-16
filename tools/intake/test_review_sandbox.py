from pathlib import Path
import unittest
from review_sandbox import command


class ReviewSandboxTests(unittest.TestCase):
    def test_only_explicit_source_provider_credentials_and_outputs_are_mounted(self):
        args=command('/tmp/source','/tmp/output','/tmp/provider-auth','/tmp/runtime')
        self.assertIn('--clearenv',args)
        self.assertIn('--unshare-all',args)
        self.assertIn('--ignore-user-config',args)
        self.assertIn('read-only',args)
        mounts=[args[i+1:i+3] for i,v in enumerate(args) if v in ('--bind','--ro-bind')]
        self.assertIn(['/tmp/provider-auth','/review-home'],mounts)
        self.assertIn(['/tmp/source','/source'],mounts)
        self.assertFalse(any(p.startswith('/home/') or p.startswith('/root/') or p.endswith('docker.sock') for pair in mounts for p in pair))


if __name__ == '__main__':
    unittest.main()
