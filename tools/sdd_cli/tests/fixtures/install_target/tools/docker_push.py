#!/usr/bin/env python3
"""
Push a Docker image to a Docker Registry v2 via the HTTP API.
Reads the image from 'docker save' output (tar on stdin or path arg).

Usage:
  docker save <image> | python3 tools/docker_push.py \\
      --registry agentic-nexus:5001 \\
      --repo sdd-test \\
      --tag latest \\
      --username admin \\
      --password admin123

Or:
  python3 tools/docker_push.py /tmp/image.tar \\
      --registry agentic-nexus:5001 \\
      --repo sdd-test \\
      --tag mytag \\
      --username admin \\
      --password admin123
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import tarfile
import urllib.error
import urllib.request

def make_auth(username, password):
    return b"Basic " + base64.b64encode(f"{username}:{password}".encode())

def request(url, method="GET", data=None, headers=None, auth=None):
    """Make an HTTP request, return (status, body_bytes, headers)."""
    rq_headers = {}
    if auth:
        rq_headers["Authorization"] = auth
    if headers:
        rq_headers.update(headers)
    if "User-Agent" not in rq_headers:
        rq_headers["User-Agent"] = "docker-push-py/1.0"
    req = urllib.request.Request(url, data=data, headers=rq_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except urllib.error.URLError as e:
        return -1, str(e.reason).encode(), {}
    except OSError as e:
        return -1, str(e).encode(), {}


def blob_exists(registry, repo, digest, auth):
    """Check if a blob already exists in the registry."""
    url = f"{registry}/v2/{repo}/blobs/{digest}"
    status, _, _ = request(url, "HEAD", auth=auth)
    return status == 200


def start_blob_upload(registry, repo, auth):
    """Start a blob upload session. Returns the upload URL."""
    url = f"{registry}/v2/{repo}/blobs/uploads/"
    status, body, headers = request(url, "POST", auth=auth)
    if status not in (201, 202):
        loc = headers.get("Location") or headers.get("location", "")
        if loc:
            if loc.startswith("http"):
                return loc
            return registry + loc
        print(f"  ERROR: Failed to start upload (HTTP {status})", file=sys.stderr)
        print(f"    Body: {body.decode(errors='replace')[:200]}", file=sys.stderr)
        return None
    loc = headers.get("Location") or headers.get("location", "")
    if not loc:
        print(f"  ERROR: No Location header in upload response (HTTP {status})", file=sys.stderr)
        return None
    if loc.startswith("http"):
        return loc
    return registry + loc


def complete_blob_upload(upload_url, digest, blob_data, auth):
    """Complete a blob upload by PUTting the data."""
    final_url = f"{upload_url}&digest={digest}" if "?" in upload_url else f"{upload_url}?digest={digest}"
    status, body, _ = request(
        final_url, "PUT",
        data=blob_data,
        headers={"Content-Type": "application/octet-stream"},
        auth=auth
    )
    if status == 201:
        return True
    print(f"  ERROR: Failed to complete blob upload (HTTP {status}): {body.decode(errors='replace')[:200]}", file=sys.stderr)
    return False


def push_blob(registry, repo, digest, blob_data, auth):
    """Push a single blob layer. Returns True on success."""
    if blob_exists(registry, repo, digest, auth):
        print(f"  Blob {digest[:20]}... exists, skip")
        return True
    upload_url = start_blob_upload(registry, repo, auth)
    if not upload_url:
        return False
    return complete_blob_upload(upload_url, digest, blob_data, auth)


def push_manifest(registry, repo, tag, manifest_bytes, auth):
    """Push an image manifest (or manifest list)."""
    # Detect content type from manifest
    try:
        m = json.loads(manifest_bytes)
    except json.JSONDecodeError:
        content_type = "application/vnd.docker.distribution.manifest.v2+json"
    else:
        if m.get("mediaType") == "application/vnd.oci.image.manifest.v1+json":
            content_type = "application/vnd.oci.image.manifest.v1+json"
        elif m.get("mediaType") == "application/vnd.docker.distribution.manifest.list.v2+json":
            content_type = "application/vnd.docker.distribution.manifest.list.v2+json"
        elif m.get("mediaType") == "application/vnd.oci.image.index.v1+json":
            content_type = "application/vnd.oci.image.index.v1+json"
        else:
            content_type = "application/vnd.docker.distribution.manifest.v2+json"
    
    url = f"{registry}/v2/{repo}/manifests/{tag}"
    status, body, _ = request(
        url, "PUT",
        data=manifest_bytes,
        headers={"Content-Type": content_type},
        auth=auth
    )
    if status == 201:
        print(f"  Manifest '{tag}' pushed")
        return True
    print(f"  ERROR: Failed to push manifest '{tag}' (HTTP {status}): {body.decode(errors='replace')[:200]}", file=sys.stderr)
    return False


def parse_save_tar(tar_path):
    """
    Parse a 'docker save' tar and extract:
      - manifest (the v2 manifest JSON bytes)
      - config (config JSON bytes)
      - layers (list of (digest, blob_data) tuples)
    Returns (manifest_bytes, layer_blobs, config_bytes, config_digest)
    """
    # Structure of docker save tar:
    # manifest.json - list of {Config, RepoTags, Layers}
    # For each layer: <layer_id>/layer.tar, <layer_id>/json, <layer_id>/VERSION
    # config file at the path specified by manifest[0].Config
    
    with tarfile.open(tar_path, "r") as tar:
        # Read manifest.json
        mf = tar.extractfile("manifest.json")
        if not mf:
            print("ERROR: No manifest.json in docker save output", file=sys.stderr)
            sys.exit(1)
        manifests = json.loads(mf.read())
        if not manifests:
            print("ERROR: Empty manifest.json", file=sys.stderr)
            sys.exit(1)
        
        manifest_info = manifests[0]
        config_path = manifest_info["Config"]
        layers_info = manifest_info.get("Layers", [])
        
        # Read config blob
        cf = tar.extractfile(config_path)
        if not cf:
            print(f"ERROR: Config file {config_path} not found in tar", file=sys.stderr)
            sys.exit(1)
        config_bytes = cf.read()
        config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
        
        # Layers from the manifest
        docker_manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {
                "mediaType": "application/vnd.docker.container.image.v1+json",
                "size": len(config_bytes),
                "digest": config_digest
            },
            "layers": []
        }
        
        layers = []
        for layer_path in layers_info:
            lf = tar.extractfile(layer_path)
            if not lf:
                print(f"  Warning: Layer {layer_path} not found, skipping", file=sys.stderr)
                continue
            layer_data = lf.read()
            layer_digest = "sha256:" + hashlib.sha256(layer_data).hexdigest()
            layers.append((layer_digest, layer_data))
            docker_manifest["layers"].append({
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": len(layer_data),
                "digest": layer_digest
            })
        
        manifest_bytes = json.dumps(docker_manifest).encode()
        return manifest_bytes, layers, config_bytes, config_digest


def main():
    parser = argparse.ArgumentParser(description="Push a Docker image to a registry via HTTP API")
    parser.add_argument("tar_path", nargs="?", default=None,
                       help="Path to docker save tar file (omit to read from stdin)")
    parser.add_argument("--registry", default=os.environ.get("REGISTRY", "agentic-nexus:5001"),
                       help="Registry host:port")
    parser.add_argument("--repo", required=True,
                       help="Repository name (e.g. sdd-test)")
    parser.add_argument("--tag", default=os.environ.get("TAG", "latest"),
                       help="Image tag")
    parser.add_argument("--username", default=os.environ.get("NEXUS_USERNAME", ""),
                       help="Registry username")
    parser.add_argument("--password", default=os.environ.get("NEXUS_PASSWORD", ""),
                       help="Registry password")
    args = parser.parse_args()
    
    if not args.username or not args.password:
        print("ERROR: --username and --password are required (or set NEXUS_USERNAME/NEXUS_PASSWORD env vars)", file=sys.stderr)
        sys.exit(1)
    
    auth = make_auth(args.username, args.password)
    registry = args.registry
    
    # Add http:// if no scheme
    if not registry.startswith("http"):
        registry = "http://" + registry
    
    # Read docker save tar
    if args.tar_path:
        if not os.path.exists(args.tar_path):
            print(f"ERROR: {args.tar_path} not found", file=sys.stderr)
            sys.exit(1)
        print(f"Reading image from {args.tar_path}...")
        manifest_bytes, layers, config_bytes, config_digest = parse_save_tar(args.tar_path)
    else:
        print("Reading image from stdin (pipe docker save)...")
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
            tmp.write(sys.stdin.buffer.read())
            tmp_path = tmp.name
        try:
            manifest_bytes, layers, config_bytes, config_digest = parse_save_tar(tmp_path)
        finally:
            os.unlink(tmp_path)
    
    repo = args.repo
    
    print(f"Target: {registry}/v2/{repo}")
    print(f"Config digest: {config_digest}")
    print(f"Layers: {len(layers)}")
    
    # Push config blob first
    print(f"Pushing config blob...")
    if not push_blob(registry, repo, config_digest, config_bytes, auth):
        print("ERROR: Failed to push config blob", file=sys.stderr)
        sys.exit(1)
    
    # Push layer blobs
    for i, (digest, data) in enumerate(layers):
        print(f"Pushing layer {i+1}/{len(layers)} ({digest[:20]}... size={len(data)} bytes)...")
        if not push_blob(registry, repo, digest, data, auth):
            print(f"ERROR: Failed to push layer {i+1} ({digest})", file=sys.stderr)
            sys.exit(1)
    
    # Push manifest
    print(f"Pushing manifest '{args.tag}'...")
    if not push_manifest(registry, repo, args.tag, manifest_bytes, auth):
        print("ERROR: Failed to push manifest", file=sys.stderr)
        sys.exit(1)
    
    print("Done!")


if __name__ == "__main__":
    main()
