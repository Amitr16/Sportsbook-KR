#!/usr/bin/env python3
import argparse, os, sys, subprocess, shutil, socket, time, re, textwrap, pathlib

ART_DIR = "pg_sync_artifacts"

def exe(path_base, name):
    return os.path.join(path_base, name) if path_base else name

def run(cmd, env=None, check=True, capture=False):
    print("🔧 Running:", " ".join(cmd))
    if capture:
        p = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(p.stdout)
        if check and p.returncode != 0:
            raise RuntimeError("command failed")
        return p.stdout
    else:
        p = subprocess.run(cmd, env=env)
        if check and p.returncode != 0:
            raise RuntimeError("command failed")
        return ""

def port_listening(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
    return False

def psql_cmd(pgbin, host, port, user, db, extra=None):
    cmd = [exe(pgbin, "psql.exe" if os.name == "nt" else "psql"),
           "-h", host, "-p", str(port), "-U", user, "-d", db]
    if extra: cmd += extra
    return cmd

def pg_dump_cmd(pgbin):
    return exe(pgbin, "pg_dump.exe" if os.name == "nt" else "pg_dump")

def ensure_artdir():
    pathlib.Path(ART_DIR).mkdir(parents=True, exist_ok=True)

def sanitize_schema_sql(s):
    # Drop CREATE/ALTER/COMMENT on public schema to avoid “schema already exists”
    patterns = [
        r"^\s*CREATE\s+SCHEMA\s+public\b.*?;\s*$",
        r"^\s*ALTER\s+SCHEMA\s+public\b.*?;\s*$",
        r"^\s*COMMENT\s+ON\s+SCHEMA\s+public\b.*?;\s*$",
    ]
    for pat in patterns:
        s = re.sub(pat, "", s, flags=re.IGNORECASE | re.MULTILINE)
    # Also remove blank lines sequences produced by deletions
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def dump_local_extensions(pgbin, host, port, user, db):
    # Generate CREATE EXTENSION IF NOT EXISTS for non-plpgsql extensions
    sql = r"\t on"
    out = run(psql_cmd(pgbin, host, port, user, db, ["-Atc",
                   "select extname from pg_extension where extname<>'plpgsql' order by 1"]),
                   capture=True)
    extnames = [ln.strip() for ln in out.splitlines() if ln.strip()]
    body = ""
    if extnames:
        body = "\n".join([f"CREATE EXTENSION IF NOT EXISTS {e};" for e in extnames]) + "\n"
    with open(os.path.join(ART_DIR, "extensions.sql"), "w", encoding="utf-8") as f:
        f.write(body)
    print(f"📝 Wrote {os.path.join(ART_DIR,'extensions.sql')} ({len(body)} bytes)")

def table_exists_local(pgbin, host, port, user, db, table):
    q = f"select to_regclass('public.{table}') is not null;"
    out = run(psql_cmd(pgbin, host, port, user, db, ["-Atc", q]), capture=True)
    return out.strip() == "t"

def dump_local_schema(pgbin, host, port, user, db):
    ensure_artdir()
    out_path = os.path.join(ART_DIR, "local_schema.sql")
    cmd = [pg_dump_cmd(pgbin),
           "-h", host, "-p", str(port), "-U", user, "-d", db,
           "--schema-only", "--schema=public", "--no-owner", "--no-privileges", "--no-comments"]
    print("📤 Dumping LOCAL schema (public, no owners/privs)...")
    with open(out_path, "w", encoding="utf-8") as f:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode != 0:
            print(p.stdout)
            raise RuntimeError("pg_dump schema failed")
        content = sanitize_schema_sql(p.stdout)
        f.write(content)
    print(f"📝 Wrote {out_path} ({os.path.getsize(out_path)} bytes)")

def dump_seed(pgbin, host, port, user, db, seed_tables):
    ensure_artdir()
    out_path = os.path.join(ART_DIR, "seed_min.sql")
    chunks = []
    for t in seed_tables:
        t = t.strip()
        if not t:
            continue
        if not table_exists_local(pgbin, host, port, user, db, t):
            print(f"ℹ️  Skipping seed for '{t}' (not found locally)")
            continue
        cmd = [pg_dump_cmd(pgbin),
               "-h", host, "-p", str(port), "-U", user, "-d", db,
               "--data-only", "-t", f"public.{t}", "--no-owner", "--no-privileges", "--column-inserts"]
        print(f"📤 Dumping seed data for table: {t}")
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode != 0:
            print(p.stdout)
            raise RuntimeError(f"pg_dump data failed for {t}")
        chunks.append(p.stdout)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(chunks))
    print(f"📝 Wrote {out_path} ({os.path.getsize(out_path)} bytes)")

def main():
    ap = argparse.ArgumentParser(description="Sync local Postgres schema/seed to Fly MPG through a local proxy.")
    # Local DB
    ap.add_argument("--local-host", default="127.0.0.1")
    ap.add_argument("--local-port", type=int, default=5432)
    ap.add_argument("--local-db", required=True)
    ap.add_argument("--local-user", required=True)
    ap.add_argument("--local-password", required=True)

    # Fly MPG connection via proxy
    ap.add_argument("--fly-cluster", required=True, help="Fly MPG cluster id (e.g., w76geopwz96rplk4)")
    ap.add_argument("--fly-region", default="iad")
    ap.add_argument("--fly-db-user", default="fly-user")
    ap.add_argument("--fly-db", default="fly-db")
    ap.add_argument("--fly-password", required=True)
    ap.add_argument("--proxy-port", type=int, default=16380)
    
    # Tools
    ap.add_argument("--pg-bin", default="", help="Directory containing psql/pg_dump if not in PATH")
    ap.add_argument("--flyctl", default="fly", help="flyctl executable name (fly or fly.exe)")

    # Data selection
    ap.add_argument("--seed-tables", default="sportsbook_operators,operator_branding,users",
                    help="Comma-separated list of tables to dump seed data for (if they exist locally)")

    # Optional: ensure tenant seed
    ap.add_argument("--ensure-tenant-subdomain", default=None)
    ap.add_argument("--ensure-tenant-name", default=None)

    # Skip flags (define once)
    ap.add_argument("--skip-extensions", dest="skip_extensions", action="store_true",
                    help="Do not dump/apply extensions")
    ap.add_argument("--skip-schema", dest="skip_schema", action="store_true",
                    help="Do not dump/apply schema DDL")
    ap.add_argument("--skip-grants", dest="skip_grants", action="store_true",
                    help="Do not apply GRANTs/default privileges (script-level)")
    ap.add_argument("--skip-seed", dest="skip_seed", action="store_true",
                    help="Do not copy seed data")

    args = ap.parse_args()

    os.environ["PGPASSWORD"] = args.local_password

    print("🚀 Starting local → Fly MPG sync")
    print("==================================================")

    # Smoke test local DB
    out = run(psql_cmd(args.pg_bin, args.local_host, args.local_port, args.local_user, args.local_db,
                       ["-Atc", "select 1"]), capture=True)
    print(out)
    print("✅ Local Postgres reachable")

    ensure_artdir()

    if not args.skip_extensions:
        print("🔍 Dumping local extensions (excluding plpgsql)...")
        dump_local_extensions(args.pg_bin, args.local_host, args.local_port, args.local_user, args.local_db)

    if not args.skip_schema:
        dump_local_schema(args.pg_bin, args.local_host, args.local_port, args.local_user, args.local_db)

    seed_tables = [t.strip() for t in args.seed_tables.split(",") if t.strip()]
    if not args.skip_seed and seed_tables:
        print(f"📤 Dumping seed data for: {', '.join(seed_tables)}")
        dump_seed(args.pg_bin, args.local_host, args.local_port, args.local_user, args.local_db, seed_tables)

    # Ensure proxy
    print(f"🔌 Ensuring proxy to Fly MPG on 127.0.0.1:{args.proxy_port} ...")
    if not port_listening("127.0.0.1", args.proxy_port):
        print("❌ Proxy not listening. In another terminal, run:")
        print(f"   {args.flyctl} mpg proxy --cluster {args.fly_cluster} --region {args.fly_region}")
        sys.exit(1)
    print("✅ Proxy is already up")

    # Target env
    env_target = os.environ.copy()
    env_target["PGPASSWORD"] = args.fly_password

    # Optional: ensure helper role (harmless)
    print("👤 Ensuring 'schema_admin' role exists (harmless if not used)...")
    run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                 ["-c", "DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='schema_admin') THEN CREATE ROLE schema_admin LOGIN; END IF; END$$;"]),
        env=env_target)

    # Apply extensions first
    if not args.skip_extensions:
        ext_file = os.path.join(ART_DIR, "extensions.sql")
        if os.path.exists(ext_file) and os.path.getsize(ext_file) > 0:
            run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                         ["-v", "ON_ERROR_STOP=1", "-f", ext_file]),
                env=env_target)
        else:
            print("ℹ️  No extensions to apply.")

    # Apply schema
    if not args.skip_schema:
        schema_file = os.path.join(ART_DIR, "local_schema.sql")
        if os.path.exists(schema_file) and os.path.getsize(schema_file) > 0:
            print("📥 Applying LOCAL schema to Fly DB...")
            try:
                run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                             ["-v", "ON_ERROR_STOP=1", "-f", schema_file]),
                    env=env_target)
            except Exception:
                print(f"❌ Failed applying {schema_file}")
                sys.exit(1)
        else:
            print("ℹ️  No schema file found/skipped.")

    # Grants for fly-user (safe to repeat)
    if not args.skip_grants:
        print("🔐 Applying basic privileges for fly-user...")
        grants = textwrap.dedent("""
            GRANT USAGE ON SCHEMA public TO "fly-user";
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "fly-user";
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "fly-user";
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "fly-user";
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "fly-user";
        """)
        run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                     ["-v", "ON_ERROR_STOP=1", "-c", grants]),
            env=env_target)

    # Seed data
    if not args.skip_seed:
        seed_file = os.path.join(ART_DIR, "seed_min.sql")
        if os.path.exists(seed_file) and os.path.getsize(seed_file) > 0:
            print("🌱 Applying seed data...")
            run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                         ["-v", "ON_ERROR_STOP=1", "-f", seed_file]),
                env=env_target)
    else:
            print("ℹ️  No seed file found/skipped.")

    # Ensure tenant row (optional)
    if args.ensure_tenant_subdomain and args.ensure_tenant_name:
        print(f"🏷️  Ensuring tenant '{args.ensure_tenant_subdomain}' exists...")
        upsert = textwrap.dedent(f"""
            DO $$
            BEGIN
              IF to_regclass('public.sportsbook_operators') IS NOT NULL THEN
                INSERT INTO public.sportsbook_operators (name, subdomain, is_active)
                VALUES ('{args.ensure_tenant_name}', '{args.ensure_tenant_subdomain}', TRUE)
                ON CONFLICT (subdomain) DO UPDATE
                  SET name = EXCLUDED.name, is_active = TRUE;
              END IF;
            END$$;
        """)
        run(psql_cmd(args.pg_bin, "127.0.0.1", args.proxy_port, args.fly_db_user, args.fly_db,
                     ["-v", "ON_ERROR_STOP=1", "-c", upsert]),
            env=env_target)

    print("\n✅ Sync complete!")

if __name__ == "__main__":
        main()
