import unittest
from scan_sources import pages, observations, repository


class ScanTests(unittest.TestCase):
    def test_registered_forges_and_raw_repository_are_mapped(self):
        self.assertEqual(repository('https://gitlab.com/group/project/-/raw/tag/assets/game.apworld'),'gitlab.com:group/project')
        self.assertEqual(repository('https://codeberg.org/o/r/releases/download/1/game.apworld'),'codeberg.org:o/r')
        self.assertEqual(repository('https://git.makuluni.com/o/r/releases/download/1/game.apworld'),'git.makuluni.com:o/r')
        self.assertEqual(repository('https://raw.githubusercontent.com/o/r/'+'a'*40+'/game.apworld'),'o/r')
        self.assertIsNone(repository('https://unregistered.test/o/r'))
    def test_paginated_arrays_are_not_truncated(self):
        self.assertEqual(pages('[{"tag_name":"v2"}]\n[{"tag_name":"v1"}]'),
                         [{'tag_name':'v2'}, {'tag_name':'v1'}])

    def test_unknown_index_anchor_does_not_suppress_releases(self):
        found, _ = observations('game', {}, [{'version':'missing-tag','url':'https://github.com/o/r/releases/download/gone/game.apworld'}],
                                [{'tag_name':'v2','assets':[{'id':1,'name':'game.apworld','browser_download_url':'https://github.com/o/r/releases/download/v2/game.apworld','updated_at':'today'}]}])
        self.assertEqual(found[0]['version'], '2')

    def test_monorepo_does_not_assign_another_games_asset(self):
        found, unmatched = observations('game', {}, [], [{'tag_name':'v2','assets':[
            {'id':1,'name':'other.apworld','browser_download_url':'https://github.com/o/r/releases/download/v2/other.apworld'}]}])
        self.assertEqual(found, [])
        self.assertEqual(unmatched, [{'tag':'v2','asset':'other.apworld'}])

    def test_existing_alias_and_asset_revision_are_preserved(self):
        url='https://github.com/o/r/releases/download/v1/game.apworld'
        release={'tag_name':'v1','assets':[{'id':7,'name':'game.apworld','browser_download_url':url,'updated_at':'a'}]}
        first,_=observations('game', {}, [{'version':'1+alias','url':url}], [release])
        release['assets'][0]['updated_at']='b'
        second,_=observations('game', {}, [{'version':'1+alias','url':url}], [release])
        self.assertEqual(first[0]['version'],'1+alias')
        self.assertNotEqual(first[0]['revision'],second[0]['revision'])


if __name__ == '__main__':
    unittest.main()
