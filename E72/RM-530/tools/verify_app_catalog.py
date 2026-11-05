#!/usr/bin/env python3
"""Validate curated metadata; optionally exercise approved live downloads (never install)."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from symport.catalog.download import Downloader
from symport.catalog.model import Catalog
from symport.catalog.packages import validate_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Download automatic entries only, using approved sources and pins')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    catalog = Catalog(args.repo / 'catalog')
    automatic = [e for e in catalog.entries.values() if e['delivery'] == 'automatic']
    downloader = Downloader(args.repo / 'build/symport/app-catalog/cache')
    results = []
    for entry in catalog.entries.values():
        source = catalog.sources[entry['source_id']]
        for artifact in source['artifacts']:
            if len(artifact['sha256']) != 64 or artifact['size'] <= 0:
                raise ValueError('Missing digest or size: ' + entry['id'])
        result = {'id': entry['id'], 'delivery': entry['delivery'], 'metadata': 'valid',
                  'network_check': 'not-run', 'handset_tested': False}
        if args.download and entry['delivery'] == 'automatic':
            try:
                artifacts = [downloader.fetch(source, a) for a in source['artifacts']]
                jar = next(((p.name, p.read_bytes()) for p, _ in artifacts if p.suffix == '.jar'), None)
                for path, evidence in artifacts:
                    validate_package(path.name, path.read_bytes(), jar)
                result.update(network_check='not-run-cache-reused' if all(e['cache_hit'] for _, e in artifacts) else 'validated',
                              package_validation='passed', artifacts=[evidence for _, evidence in artifacts])
            except (ValueError, OSError) as exc:
                result.update(network_check='failed', error=str(exc))
        results.append(result)
    report = {'checked_at': datetime.now(UTC).isoformat(), 'curated': len(catalog.entries),
              'automatic': len(automatic), 'manual': len(catalog.entries) - len(automatic),
              'results': results, 'installation_tested': False}
    path = args.repo / 'build/reports/catalog-validation.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Catalog: {report['curated']} entries, {report['automatic']} automatic, {report['manual']} manual")
    print(f'Report: {path}')
    raise SystemExit(1 if any(r['network_check'] == 'failed' for r in results) else 0)


if __name__ == '__main__':
    main()
