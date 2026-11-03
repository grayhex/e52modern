# Test fixtures from the real SDK

Built on 2026-11-03 with **symbian-platform 0.3.0** (Apache-2.0, https://github.com/hpnkv/symbian-platform),
system Clang 18 / LLD 18 / CMake 3.28 / Ninja 1.13, target `armv5t`:

| File | Origin |
|---|---|
| `e32_probe_armv5t.exe` | `symbian build --project probes/e32_probe --architecture armv5t` (348 bytes, UID3 0xE0000808, no imports) |
| `e32_probe_armv5t.sdk-inspect.json` | `symbian --output-format json inspect --format e32` on that file |
| `sdk_probe_package.sis` | `symbian package` of that executable (UID 0xE0000809, unsigned) |
| `sdk_probe_package.sdk-inspect.json` | `symbian ... inspect --format sis` on it |
| `sdk_probe_package_signed.sis` | `symbian signing sign` with a throw-away self-signed identity ("SymPort test only"); contains only the public certificate, the private key was not kept |

They are small build outputs of Apache-2.0 sources and are used only to check that SymPort's parsers agree with an
independent implementation. They say nothing about acceptance by Nokia E52 firmware: no SIS here was installed on a phone
and no image was run in an emulator. The SDK's import-table path was not exercised (see docs/STATUS.md).
