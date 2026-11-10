import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'hunyuan_web.mjs'

@unittest.skipUnless(shutil.which('node'), 'Node unavailable')
class HunyuanGateTests(unittest.TestCase):
    def js(self, body):
        code = "const m = await import(" + json.dumps(SCRIPT.as_uri()) + ");\n" + body
        p = subprocess.run(['node', '--input-type=module', '-e', code], text=True, encoding="utf-8", capture_output=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_invalid_mode_stops_before_project_or_browser(self):
        p = subprocess.run(['node', str(SCRIPT), '--mode', 'typo'], capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('submit', p.stderr)

    def test_submit_requires_confirmation_before_browser(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run(['node', str(SCRIPT), '--mode', 'submit', '--project', d], capture_output=True, text=True, encoding="utf-8", timeout=10)
            self.assertEqual(p.returncode, 10, p.stderr)
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_status_and_download_without_context_stop_offline(self):
        with tempfile.TemporaryDirectory() as d:
            for mode in ['status','download']:
                p = subprocess.run(['node', str(SCRIPT), '--mode', mode, '--project', d], capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertEqual(p.returncode, 11, p.stderr)
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_unknown_quota_is_not_zero_or_guessed(self):
        self.assertEqual(self.js("console.log(JSON.stringify([m.parseQuota('4'),m.parseQuota('unknown'),m.parseQuota('0'),m.parseQuota('积分 4/10')]));"), [4,None,0,None])

    def test_quota_unknown_empty_and_mismatch_have_real_exit_codes(self):
        result=self.js("console.log(JSON.stringify([null,0,4,3].map(v=>{try{return m.validateSubmitQuota(v,4)}catch(e){return e.exitCode}})));")
        self.assertEqual(result,[12,12,4,10])

    def test_context_requires_exact_task_id_on_result_url(self):
        result=self.js("const base={taskId:'abc',submittedAt:new Date().toISOString()};let out=[];for(const resultPageUrl of ['https://3d.hunyuan.tencent.com/result/abc','https://3d.hunyuan.tencent.com/creation?taskId=abc','https://3d.hunyuan.tencent.com/result/abcdef','https://other.test/result/abc','broken']){try{m.checkedContext({...base,resultPageUrl});out.push(0)}catch(e){out.push(e.exitCode)}} console.log(JSON.stringify(out));")
        self.assertEqual(result,[0,0,11,11,11])

    def test_every_slot_must_have_identity_thumbnail_and_complete_state(self):
        result = self.js("const slots=m.VIEWS.map(v=>({slot:v.slot,file:v.file,thumbnail:true,complete:true,uploading:false})); console.log(JSON.stringify([m.uploadsComplete(slots),m.uploadsComplete(slots.map((s,i)=>i===3?{...s,uploading:true}:s)),m.uploadsComplete(slots.map((s,i)=>i===4?{...s,file:'wrong.png'}:s)),m.uploadsComplete(slots.slice(1))]));")
        self.assertEqual(result, [True,False,False,False])

    def test_old_thumbnail_or_unknown_completion_cannot_pass_for_new_input(self):
        result = self.js("const slots=m.VIEWS.map(v=>({slot:v.slot,file:v.file,thumbnail:true,complete:true,uploading:false,fileMatchesExpectedHash:true,thumbnailUpdated:true,thumbnailMatchesFile:true,serverComplete:true})); const checks=[slots,slots.map((s,i)=>i===2?{...s,thumbnailUpdated:false}:s),slots.map((s,i)=>i===2?{...s,serverComplete:'unknown'}:s),slots.map((s,i)=>i===2?{...s,thumbnailMatchesFile:'unknown'}:s),slots.map((s,i)=>i===2?{...s,fileMatchesExpectedHash:false}:s)]; console.log(JSON.stringify(checks.map(m.uploadsComplete)));")
        self.assertEqual(result,[True,False,False,False,False])

    def test_confirmation_binds_project_hashes_and_configuration(self):
        result = self.js("const c={confirmedAt:new Date().toISOString(),project:'/project',imageSha256:Array(8).fill('a'.repeat(64)),quotaBefore:4,modelVersion:'3.1',faces:1500000,generateType:'Normal'};const expected={project:'/project',imageSha256:c.imageSha256,modelVersion:'3.1',faces:1500000,generateType:'Normal'};let out=[];for(const v of [c,{...c,quotaBefore:0},{...c,project:'/other'},{...c,imageSha256:Array(8).fill('b'.repeat(64))},{...c,confirmedAt:'not-time'},{...c,generateType:'Geometry'}]){try{m.validateConfirmation(v,expected);out.push(true)}catch{out.push(false)}} console.log(JSON.stringify(out));")
        self.assertEqual(result,[True,False,False,False,False,False])

    def test_glb_checks_magic_size_declared_length_and_hash(self):
        result=self.js("const b=Buffer.alloc(1048577);b.write('glTF');b.writeUInt32LE(2,4);b.writeUInt32LE(b.length,8);let out=[];for(const v of [b,Buffer.alloc(1048577),b.subarray(0,32)]){try{out.push(m.inspectGlb(v).sha256.length===64)}catch{out.push(false)}} console.log(JSON.stringify(out));")
        self.assertEqual(result,[True,False,False])

    def test_upload_rejects_foreign_page_before_browser(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run(['node', str(SCRIPT), '--mode', 'upload', '--project', d,
                                '--url', 'https://3d.hunyuan.tencent.com.example.test/creation'],
                               capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(2, p.returncode, p.stderr)
            self.assertEqual(list(pathlib.Path(d).iterdir()), [])

    def test_confirmation_identity_ignores_json_order_and_extra_fields(self):
        result = self.js("const c={confirmedAt:'2026-01-01T00:00:00Z',project:'/project',imageSha256:Array(8).fill('a'.repeat(64)),quotaBefore:4,modelVersion:'3.1',faces:1500000,generateType:'Normal'}; const reordered=Object.fromEntries(Object.entries(c).reverse()); console.log(JSON.stringify([m.confirmationDigest(c) === m.confirmationDigest({...reordered,notes:'same approval'}), m.confirmationDigest(c) !== m.confirmationDigest({...c,confirmedAt:'2026-01-01T00:01:00Z'})]));")
        self.assertEqual([True, True], result)

if __name__ == '__main__':
    unittest.main()
