import Workbench, { Updates } from './Workbench';

/** Device diagnostics: the manual E52 test protocol plus the firmware reference. */
export default function Diagnostics() {
  return (
    <>
      <Workbench page="device" />
      <section id="diagnostics-updates" aria-label="Firmware updates">
        <Updates heading={false} />
      </section>
    </>
  );
}
