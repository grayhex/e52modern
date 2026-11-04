import Workbench from './Workbench';

/** SDK and build: application projects plus the toolchain environment check. */
export default function Sdk() {
  return (
    <>
      <Workbench page="apps" />
      <section id="sdk-environment" aria-label="Environment">
        <Workbench page="overview" heading={false} />
      </section>
    </>
  );
}
