# Device Agent — manual hardware checklist (E52 FP2, N95 FP1)

Run only with a phone you own, a backup of your data and the build under test. Record every result as
*what you saw*. Nothing in CI substitutes for these steps.

1. Inspector: structure/CRC, platform UID (FP1 `0x102032BE` or FP2 `0x102752AE`), capabilities requested, signature state.
2. Install on the phone yourself (SymPort never installs). Note any installer warning.
3. Pairing: code shown by the host is accepted; a wrong code is rejected; an expired code is rejected.
4. Each read operation with its permission granted: values plausible; with the permission missing: refused.
5. Permission expiry and `revoke` take effect at once; disconnect forgets the pairing; restart requires pairing again.
6. `file.echo-test` and `file.send`: the phone asks for consent; declining writes nothing; accepting writes only inside `SymPort-*`; the read-back hash matches.
7. `install.open`: the normal installer opens, nothing installs without your own confirmation.
8. `export.contacts`: consent prompt appears; the payload hash matches; only the chosen fields leave the phone.
9. Forbidden operations are refused by the host and never reach the phone.
10. Uninstall the agent: all other SymPort functions are unchanged.
