#!/usr/bin/env python3

import sys, os, json, urllib.request, tarfile, io, shutil, hashlib

ROOT=os.path.expanduser("~/.rks")
DB=os.path.expanduser("~/.rks_db.json")
BIN=os.path.expanduser("~/.local/bin")

# ---------------- DB ----------------

def load():
    return json.load(open(DB)) if os.path.exists(DB) else {"packages":{}}

def save(d):
    os.makedirs(ROOT, exist_ok=True)
    json.dump(d, open(DB,"w"), indent=2)

# ---------------- SECURITY (SIMULATED SIGNATURE) ----------------

def hash_data(data):
    return hashlib.sha256(data).hexdigest()

# ---------------- PACKAGE FETCH ----------------

def fetch(pkg):
    try:
        name,ver=(pkg.split("@")+["latest"])[:2] if "@" in pkg else (pkg,"latest")

        with urllib.request.urlopen(f"https://registry.npmjs.org/{name}") as r:
            j=json.loads(r.read().decode())

        if "dist-tags" not in j:
            return None,None,None,None

        ver=j["dist-tags"]["latest"] if ver=="latest" else ver

        if ver not in j["versions"]:
            return None,None,None,None

        v=j["versions"][ver]

        return name,ver,v["dist"]["tarball"],v.get("dependencies",{})

    except Exception as e:
        print("DEBUG FETCH ERROR:", e)
        return None,None,None,None

# ---------------- INSTALL ENGINE ----------------

def install_pkg(db,name,ver,url,deps):
    path=f"{ROOT}/{name}/{ver}"
    os.makedirs(path,exist_ok=True)

    data=urllib.request.urlopen(url).read()

    tar=tarfile.open(fileobj=io.BytesIO(data))
    tar.extractall(path)

    db["packages"].setdefault(name,{})
    db["packages"][name][ver]={
        "path":path,
        "deps":deps,
        "hash":hash_data(data)
    }

# ---------------- DEPENDENCY RESOLVER ----------------

def resolve(db,name,ver,url,deps,seen=None):
    if seen is None:
        seen=set()

    if name in seen:
        return

    seen.add(name)

    for d in deps:
        n,v,u,dd=fetch(d)
        if n:
            resolve(db,n,v,u,dd,seen)

    install_pkg(db,name,ver,url,deps)

# ---------------- CORE INSTALL ----------------

def install(db,pkg):
    name,ver,url,deps=fetch(pkg)
    if not url:
        print("ERROR: package not found")
        return db

    resolve(db,name,ver,url,deps)
    print("INSTALLED:",name,ver)
    return db

# ---------------- REMOVE ----------------

def uninstall(db,name):
    if name in db["packages"]:
        for v in db["packages"][name]:
            shutil.rmtree(db["packages"][name][v]["path"],ignore_errors=True)
        del db["packages"][name]
        print("REMOVED:",name)
    return db

# ---------------- UPDATE ----------------

def update(db,pkg):
    return install(db,pkg)

# ---------------- ROLLBACK ----------------

def rollback(db,name):
    if name in db["packages"]:
        versions=list(db["packages"][name].keys())
        if len(versions)>1:
            last=versions[-1]
            shutil.rmtree(db["packages"][name][last]["path"],ignore_errors=True)
            del db["packages"][name][last]
            print("ROLLED BACK:",name)
    return db

# ---------------- LIST ----------------

def listp(db):
    for k,v in db["packages"].items():
        print(k,"=>",list(v.keys()))

# ---------------- STATUS ----------------

def status(db):
    print("RKS STATUS")
    print("Packages:",len(db["packages"]))

# ---------------- INSTALL CLI ----------------

def link():
    os.makedirs(BIN,exist_ok=True)
    with open(f"{BIN}/rks","w") as f:
        f.write(f"#!/usr/bin/env python3\nimport rks\n")
    os.chmod(f"{BIN}/rks",0o755)
    print("GLOBAL COMMAND INSTALLED: rks")

# ---------------- MAIN ----------------

def main():
    db=load()
    args=sys.argv[1:]
    i=0

    while i<len(args):
        a=args[i]

        if a=="--install":
            db=install(db,args[i+1]); i+=1

        elif a=="--uninstall":
            db=uninstall(db,args[i+1]); i+=1

        elif a=="--update":
            db=update(db,args[i+1]); i+=1

        elif a=="--rollback":
            db=rollback(db,args[i+1]); i+=1

        elif a=="--list":
            listp(db)

        elif a=="--status":
            status(db)

        elif a=="--version":
            print(VERSION)

        elif a=="--link":
            link()

        i+=1

    save(db)

main()
