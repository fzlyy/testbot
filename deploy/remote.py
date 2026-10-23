#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Minimal SSH/SFTP helper (paramiko) for provisioning the Aliyun ECS box.

Credentials come from the environment so nothing secret is written to disk:
    AHOST, AUSER, APASS  (or APASS_FILE, or AKEY pointing at an OpenSSH key)

Usage:
    python deploy/remote.py run "uname -a"
    python deploy/remote.py run --file local_script.sh      # upload+run a script
    python deploy/remote.py put local_path remote_path
    python deploy/remote.py get remote_path local_path
"""
import os
import sys
import argparse

import paramiko

HOST = os.environ.get("AHOST", "")
USER = os.environ.get("AUSER", "root")
PORT = int(os.environ.get("APORT", "22"))
PASS = os.environ.get("APASS", "")
PASS_FILE = os.environ.get("APASS_FILE", "")
KEY = os.environ.get("AKEY", "")

if PASS_FILE:
    with open(PASS_FILE, "rb") as f:
        PASS = f.read().decode("utf-8").strip()


def connect():
    if not HOST:
        sys.exit("AHOST is not set")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = dict(hostname=HOST, port=PORT, username=USER, timeout=20,
                  banner_timeout=30, auth_timeout=30, allow_agent=False,
                  look_for_keys=False)
    if KEY:
        kwargs["key_filename"] = KEY
        kwargs["passphrase"] = PASS or None
    else:
        kwargs["password"] = PASS
    c.connect(**kwargs)
    return c


def run(c, cmd, timeout=1800):
    chan = c.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out, err = [], []
    while True:
        if chan.recv_ready():
            out.append(chan.recv(65536))
        if chan.recv_stderr_ready():
            err.append(chan.recv_stderr(65536))
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
    code = chan.recv_exit_status()
    return (b"".join(out).decode("utf-8", "replace"),
            b"".join(err).decode("utf-8", "replace"),
            code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["run", "put", "get"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--file", default=None)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    c = connect()
    try:
        if a.action == "run":
            if a.file:
                sftp = c.open_sftp()
                remote = "/tmp/dsh_%s" % os.path.basename(a.file)
                sftp.put(a.file, remote)
                sftp.close()
                cmd = "bash %s" % remote
                if a.args:
                    cmd += " " + " ".join(a.args)
            else:
                cmd = a.args[0] if a.args else sys.stdin.read()
            out, err, code = run(c, cmd, a.timeout)
            sys.stdout.write(out)
            if err.strip():
                sys.stderr.write("\n--- stderr ---\n" + err)
            print("\n[remote exit %d]" % code)
            return code
        if a.action == "put":
            sftp = c.open_sftp()
            sftp.put(a.args[0], a.args[1])
            sftp.close()
            print("uploaded %s -> %s" % (a.args[0], a.args[1]))
            return 0
        if a.action == "get":
            sftp = c.open_sftp()
            sftp.get(a.args[0], a.args[1])
            sftp.close()
            print("downloaded %s -> %s" % (a.args[0], a.args[1]))
            return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
