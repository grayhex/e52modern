# Catalog P1: original-source review

Reviewed 2026-11-04. Scope: Nokia E52/E72, Symbian 9.3 / S60 3rd FP2.
Index: [awesome-symbian, pinned revision ed79fd5](https://github.com/hstsethi/awesome-symbian/blob/ed79fd54fc5c46640faf65adac39d70f3cdf0a1b/readme.md).
The index's CC0 license grants no rights to the listed software.

| App | Original source / license | Distribution / E52–E72 decision |
|---|---|---|
| Opera Mini | [Opera](https://www.opera.com/mobile/mini), proprietary freeware | Both historical Java download paths on `mini.opera.com` returned HTTP 503 during this review. The current site offers Android. No validated original JAR/JAD/version/hash or redistribution grant: manual author link, unavailable status. Do not substitute Android Opera, Opera Mobile or a mirror repack. |
| FShell | [d3ru/FShell](https://github.com/d3ru/FShell/tree/60781839df208eae281dde0350bc3d2a572fbb69), EPL-1.0 headers | `README_HowToBuild` includes `s60/3rd_edition`, but no full release SIS. `clogger-stub.SIS` (1304 bytes) is a library ROM stub, not FShell. Source-only, untested. Building/signing and restricted commands require a separately reviewed SDK/capability setup. |
| QRemoteControl | [machinekoder/QRemoteControl-Client](https://github.com/machinekoder/QRemoteControl-Client/tree/ba5652a571660c9986a0158a8c24eb3e8bda4380), GPL-3.0 `gpl.txt` | The original strahlex URL redirects here. No release artifacts/tags or Symbian branch found. Master reports 2.6.1 and uses Qt Quick/Qt 5 code; this does not prove an E52-compatible SIS. Requires its PC server and matching Qt client. Manual source, unavailable. No GPL client code copied into SymPort. |
| Internet Radio | [fedor4ever/internet-radio](https://github.com/fedor4ever/internet-radio/tree/61e1763b623915f1acf5064a8ab8a9d2ad5bc59e), Nokia EPL-1.0 headers | Native `internetradio2.0` package source declares 1.1.0; Qt is a separate variant. Only `ir3_qtinternetradio_stub.sis` (2556 bytes) exists in the tree, not an installable player. No full signed author distribution or station-directory availability confirmed. Manual source, unavailable. |
| X-plore | [Lonely Cat Games](https://www.lonelycatgames.com/apps/xplore-symbian) | Existing reviewed 1.64 entry reused, not duplicated. Original author download already automatic/hash-pinned; expiry and S60 compatibility caveats remain. See [XPLORE.md](XPLORE.md). |
| Rotate It! | [author v0.2.1](https://github.com/vitalii17/RotateIt/releases/tag/v0.2.1), MIT source / separate Exiv2 terms | Original SIS obtained/parsed; Qt 4.7.4 + Qt Quick Components 1.1. Author targets 9.4/Anna/Belle. **Unsupported on E52/E72**, manual author link. |
| NanoCounter | [author v0.1.1](https://github.com/vitalii17/NanoCounter/releases/tag/v0.1.1), MIT source | Original SIS obtained/parsed; Qt >=4.7.3. Author specifies 9.4–Belle FP2; target-device UIDs are touch/Symbian^3. **Unsupported on E52/E72**. Original controller/data CRC fields are absent, not claimed verified. |
| FileList | [Nokia/Microsoft sample](https://github.com/ltomuta/filelist/tree/be3528abaf6bdc28593a2184bdb0ab7318289e59), device-limited `Licence.txt` | Original 1.1 SIS obtained/parsed. Qt 4.7.4, Mobility >=1.2, Qt Quick Components >=1.0 in SIS (README recommends 1.1). Symbian^3/Anna target UIDs. **Unsupported on E52/E72**. This license is not BSD/MIT. |

Additional review: Fahrplan's author README targets Symbian touch/Anna/Belle, so its
SIS is not promoted as E52 compatible. Whisk3D's current source describes N95/OpenGL
ES 1.1, but its pre-alpha release has no assets; no verified E52 binary was inferred.
RomBrowser is a desktop .NET tool and was not added to the phone-app catalog.

## Measured SHA-256

Only actual downloaded files have hashes. No ROM, stub, application binary or key
is committed or baked into Docker. Reproducible source URLs, byte counts, UID/version,
dependency declarations and checksum results are in `catalog/sources.json`.

| Original artifact | Bytes | SHA-256 |
|---|---:|---|
| Rotate_It.sis | 855268 | `b8dd8f0baf31b7ebaddbde6c62af216c85d8899a492ed9375cb50847b826ed79` |
| NanoCounter.sis | 26416 | `d429181e3aa58afc022b46baa62fb373b3e2b9496b7898dc27fd4f3bb3d3580e` |
| FileListQML_v1_1-1.sis | 33548 | `26a9cb03c7a3f609ab5639e97fa6a1d32c9ce0d12725b6c98e6d5e971cc721a4` |

These are measured pins, not publisher-issued checksums or proof of trusted signing.
SIS checksum/dependency parsing does not demonstrate installation, network service
availability or execution on any phone. Existing automatic downloads remain in use
for approved distributions. Missing/unsupported P1 binaries have source links and
cannot enter recovery transfer batches; compatible originals can be supplied later
through the normal upload → Inspector → Lab/phone flow after review.

Catalog defaults to usable candidate states; choose **All compatibility states** to
see source-only unavailable and incompatible entries, including their exact reasons.
A source-only card links to its author's repository/site, never to an invented package.
