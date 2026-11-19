#!/usr/bin/env python3
"""Exact 158 product toolchain preparation. Caller owns process-group deadline.

No acquisition, global package installation/configuration, or old graph reuse.
"""
import argparse,ast,hashlib,json,os,re,shlex,subprocess
from pathlib import Path
import source

HASHES={'core_wrapper':'f79af458ca24db5b772c7e93e212b733dea07da24f27342f5e03af8ff07549db','core_siso':'bff0364e2ea33f83136ee4c24a3b2d6b32a7a36d273e6330d20f0c49416c17f0','compiler':'251c239416334d20a7c34eebd2b345dfe81359e83ab2c57d196bb96c8cb0a0c4','backend':'032a09413eacc1da6f5fa27340c1542e66f54fc4355b8a0dffbc03b34f96e0cd'}
COMPILER_OLD='clang_diagnostic_dir = rebase_path("//out/clang-crashreports", root_build_dir)'
COMPILER_NEW='clang_diagnostic_dir = "clang-crashreports"'
WRAPPER_OLD='''    FileUtils.write_text_file(
        (
            f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'
            'python_remote_wrapper'
        ),
        ShellTemplate(python_remote_wrapper_template).substitute(template_vars),
    )'''
WRAPPER_NEW='''    wrapper_path = (
        f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'
        'python_remote_wrapper'
    )
    FileUtils.write_text_file(
        wrapper_path,
        ShellTemplate(python_remote_wrapper_template).substitute(template_vars),
    )
    os.chmod(wrapper_path, 0o755)'''
SISO_ANCHOR='    __remove_labels_from_platforms(step_config)\n'
SISO_NEW=SISO_ANCHOR+'''
    # Sandium: materialize canonical REAPI working directory on BuildBuddy.
    for rule in step_config["rules"]:
        if rule.get("remote", False):
            rule["canonicalize_dir"] = True
            inputs = rule.get("inputs", [])
            if "./args.gn" not in inputs:
                inputs.append("./args.gn")
            rule["inputs"] = inputs
'''

def transform(kind,text):
    old,new={'compiler':(COMPILER_OLD,COMPILER_NEW),'core_wrapper':(WRAPPER_OLD,WRAPPER_NEW),'core_siso':(SISO_ANCHOR,SISO_NEW)}[kind]
    # Reverse only an exact postimage, then authenticate the whole upstream file.
    original=text
    if new in text:
        if text.count(new)!=1:raise ValueError('Ambiguous patched toolchain file: '+kind)
        original=text.replace(new,old,1)
    if hashlib.sha256(original.encode()).hexdigest()!=HASHES[kind] or original.count(old)!=1:
        raise ValueError('Unreviewed 158 toolchain source: '+kind)
    return original.replace(old,new,1)

def sisorc(text):
    lines=text.splitlines();indexes=[i for i,l in enumerate(lines) if l.strip() and not l.lstrip().startswith('#') and shlex.split(l)[0]=='ninja']
    if len(indexes)!=1:raise ValueError('Exactly one native Siso ninja command required')
    index=indexes[0];tokens=shlex.split(lines[index])
    for sequence in (['-reapi_keep_exec_stream'],['-fs_min_flush_timeout','300s'],['-reapi_byte_stream_read_threshold','1024']):
        if not any(tokens[i:i+len(sequence)]==sequence for i in range(len(tokens))):raise ValueError('Missing native Siso flags')
    if any(t.startswith(('-re_exec_enable=false','-re_cache_enable_write=false')) for t in tokens):raise ValueError('Read-only/local-only Siso config conflicts with reviewed build')
    positions=[i for i,t in enumerate(tokens) if t=='-config']
    if len(positions)!=1 or positions[0]+1>=len(tokens):raise ValueError('Native Siso config missing')
    n=positions[0]+1;configs=tokens[n].split(',')
    if 'googlechrome' not in configs:raise ValueError('Native googlechrome Siso rules required')
    if 'remote-link' not in configs:configs.append('remote-link')
    tokens[n]=','.join(configs)
    if '-re_cache_enable_write=true' not in tokens:tokens.append('-re_cache_enable_write=true')
    lines[index]=shlex.join(tokens)
    return '\n'.join(lines)+'\n'

def environment(root):
    env=dict(os.environ,CIRCLE_WORKING_DIRECTORY=str(root),DEPOT_TOOLS_UPDATE='0',SISO_LIMITS='local=8,remote=80')
    env['npm_config_store_dir']=str(root/'brave-work/.sandium/pnpm-store')
    return env

def command(args,root,**kwargs):
    return subprocess.run(args,cwd=root/'brave-work/src/brave',env=environment(root),check=True,**kwargs)

def context(root):
    root=Path(root).resolve();source.verify(root/'brave-work')
    return root,root/'brave-work/src',root/'brave-work/src/brave'

def prepare(root):
    root,src,core=context(root)
    paths={'compiler':src/'build/config/compiler/compiler.gni','core_wrapper':core/'third_party/reclient_configs/brave_custom/brave_custom.py','core_siso':core/'build/config/siso/brave_siso_config.star'}
    generated=src/'build/config/siso/brave_siso_config.star'
    # Validate all exact pre/postimages before editing any.
    planned=[(p,transform(k,p.read_text())) for k,p in paths.items()]
    planned.append((generated,transform('core_siso',generated.read_text())))
    for path,text in planned:path.write_text(text)
    wrapper=src/'buildtools/reclient_cfgs/python/python_remote_wrapper'
    if not wrapper.is_file() or not wrapper.stat().st_size:raise ValueError('Native generated Python wrapper missing')
    wrapper.chmod(0o755)
    remote(root)

def remote(root):
    root,src,core=context(root)
    address=os.environ.get('SANDIUM_REAPI_ADDRESS') or 'remote.buildbuddy.io:443'
    if not re.fullmatch(r'[A-Za-z0-9.-]+:443',address):raise ValueError('Invalid REAPI endpoint')
    helper=Path('/tmp/sandium-buildbuddy-credential-helper.py')
    if not helper.is_file() or not os.access(helper,os.X_OK):raise ValueError('Runner credential helper missing')
    directory=src/'build/config/siso';backend=directory/'backend_config/google.star'
    text=backend.read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=HASHES['backend']:raise ValueError('Unreviewed pinned backend')
    images=[ast.literal_eval(l.partition('=')[2].strip()) for l in text.splitlines() if l.partition('=')[0].strip()=='container_image']
    if len(images)!=1 or not images[0].startswith('docker://'):raise ValueError('Pinned Chromium image missing')
    command(['python3',str(directory/'configure_siso.py'),'--reapi_instance','default','--reapi_address',address,'--reapi_backend_config_path',str(backend),'--credential-helper',str(helper)],root)
    if images[0] not in (directory/'backend_config/backend.star').read_text():raise ValueError('Generated backend image differs')
    rc=directory/'.sisorc';rc.write_text(sisorc(rc.read_text()))
    env=(directory/'.sisoenv').read_text().splitlines()
    for item in ('SISO_REAPI_ADDRESS='+address,'SISO_REAPI_INSTANCE=default','SISO_CREDENTIAL_HELPER='+str(helper)):
        if env.count(item)!=1:raise ValueError('Generated Siso environment mismatch')
    bash_env=os.environ.get('BASH_ENV')
    if bash_env:
        with open(bash_env,'a') as f:
            for k,v in {'SISO_REAPI_ADDRESS':address,'SISO_REAPI_INSTANCE':'default','SISO_LIMITS':'local=8,remote=80'}.items():f.write('export '+k+'='+shlex.quote(v)+'\n')
    return {'backend_image':images[0],'reapi_address':address}

GN_ARGS={'use_siso':'true','use_reclient':'false','is_official_build':'true','is_debug':'false','is_component_build':'false','symbol_level':'1','is_java_debug':'false','enable_android_secondary_abi':'false','dcheck_always_on':'false','dcheck_is_configurable':'false','enable_expensive_dchecks':'false','enable_java_asserts':'false','chrome_pgo_phase':'0','use_thin_lto':'true','use_lld':'true','use_mold':'false','enable_updater':'false','enable_update_notifications':'false','android_channel':'default','chrome_public_manifest_package':'com.brave.browser_default','brave_channel':'development','enable_brave_talk':'false','enable_brave_wayback_machine':'false','enable_speedreader':'false','enable_tor':'false','enable_web_discovery_native':'false','enable_web_discovery':'false'}
def gn_command():
    args=['pnpm','run','build','Release','--target_os=android','--target_arch=arm64','--target_android_output_format=apk','--use_remoteexec=true','--force_gn_gen']
    for k,v in GN_ARGS.items():args+=['--gn',k+':'+v]
    return args+['--target','brave','--ninja=n']

def gn(root):
    root,src,core=context(root)
    command(['node',str(root/'.circleci/scripts/prepare-official-service-placeholders.mjs'),str(core)],root)
    # Native upstream dryrun performs GN generation; never take legacy reuse path.
    command(gn_command(),root)
    prepare(root)  # Native dryrun may regenerate runtime .sisorc/wrapper files.
    verify(root)

def verify(root):
    root,src,core=context(root)
    for kind,path in [('compiler',src/'build/config/compiler/compiler.gni'),('core_wrapper',core/'third_party/reclient_configs/brave_custom/brave_custom.py'),('core_siso',core/'build/config/siso/brave_siso_config.star'),('core_siso',src/'build/config/siso/brave_siso_config.star')]:
        value=path.read_text()
        if transform(kind,value)!=value:raise ValueError('Toolchain normalization missing')
    command(['bash',str(root/'.circleci/scripts/verify-clang-diagnostics-gn.sh')],root)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','gn','verify'));parser.add_argument('--root',required=True,type=Path);args=parser.parse_args()
    globals()[args.phase](args.root)
