import assert from 'node:assert/strict';
import test from 'node:test';
import { load } from 'js-yaml';
import { buildYamlContent } from '../../src/lib/yamlBuild.ts';

test('unresolved defaults stay absent, explicit empty lists stay explicit', () => {
  const template = {game:'Fixture', ap_version:'', world_version:'', categories:[], options:[
    {name:'arenas', type:'list' as const, description:'', category:'', default:null, default_unresolved:true},
    {name:'empty', type:'list' as const, description:'', category:'', default:[]},
  ]};
  const emit = (values: Record<string, unknown>) => (load(buildYamlContent({
    playerName:'AppieCTR', game:'Fixture', worldVersion:'', template, values,
  })) as Record<string, Record<string, unknown>>).Fixture;
  assert.deepEqual(emit({arenas:null}), {empty:[]});
  assert.deepEqual(emit({}), {empty:[]});
  assert.deepEqual(emit({arenas:[]}), {arenas:[], empty:[]});
  assert.deepEqual(emit({arenas:['Nitro Court']}), {arenas:['Nitro Court'], empty:[]});
});
