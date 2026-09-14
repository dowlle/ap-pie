"""Restricted headless review environment with provider-only credentials.

The broker supplies a private directory containing only auth.json. Never mount
the real home, app checkout, Docker socket or application environment here.
"""
from pathlib import Path


def command(source, output, auth, runtime, *, model='gpt-5.6-luna'):
    args=['/usr/bin/bwrap','--die-with-parent','--new-session','--unshare-all','--share-net',
          '--clearenv','--setenv','PATH','/opt/codex:/usr/bin:/bin',
          '--setenv','HOME','/review-home','--setenv','CODEX_HOME','/review-home',
          '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc',
          '--dir','/etc/ssl','--ro-bind','/etc/ssl/certs','/etc/ssl/certs']
    for name in ('resolv.conf','hosts','nsswitch.conf'):
        path=Path('/etc')/name
        if path.exists():args+=['--ro-bind',str(path),str(path)]
    args+=['--ro-bind',str(Path(runtime).resolve()),'/opt/codex',
           '--ro-bind',str(Path(source).resolve()),'/source',
           '--bind',str(Path(output).resolve()),'/output',
           '--bind',str(Path(auth).resolve()),'/review-home','--chdir','/source',
           '/opt/codex/codex','exec','--model',model,'--ephemeral','--skip-git-repo-check',
           '--sandbox','read-only','--ignore-user-config','--output-last-message','/output/report.md','--json','-']
    return args
