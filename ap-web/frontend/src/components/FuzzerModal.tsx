import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import type { FuzzResult } from "../api";

const meanings = {
  clean: "Low failure rates in the recorded checks. Clean does not mean zero failures or guaranteed success.",
  flaky: "Some checks found reliability problems. Particular settings or seeds may fail.",
  broken: "The recorded checks found substantial generation problems. This does not mean every settings combination fails.",
};

export default function FuzzerModal({ result, version, onClose }: {
  result: FuzzResult; version?: string; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const close = () => {
    dialog.current?.close();
    onClose();
  };
  useEffect(() => {
    const element = dialog.current!;
    element.showModal();
    return () => element.close();
  }, []);

  return createPortal(
    <dialog ref={dialog} className="settings-modal fuzzer-modal" aria-labelledby={titleId}
      onCancel={(event) => { event.preventDefault(); close(); }}
      onClick={(event) => { event.stopPropagation(); if (event.target === event.currentTarget) close(); }}>
      <header className="settings-modal-header">
        <h2 id={titleId}>What is the fuzzer?</h2>
        <button type="button" className="btn btn-sm" onClick={close} aria-label="Close fuzzer explanation">×</button>
      </header>
      <div className="settings-modal-body">
        <p>The fuzzer repeatedly tries to generate an Archipelago world with randomized settings and seeds. Extra checks look for problems in the world’s generation code.</p>
        <section className="fuzzer-record" aria-label="Recorded result">
          <h3>{version ? `Version ${version}` : "Selected APWorld version"}: <span className={`fuzz-pill-${result.verdict}`}>{result.verdict}</span></h3>
          <p>{meanings[result.verdict]}</p>
          <dl>
            <div><dt>Randomized generation failures</dt><dd>{(result.default_rate * 100).toFixed(2)}%</dd></div>
            <div><dt>Highest recorded check failure rate</dt><dd>{(result.worst_hook_rate * 100).toFixed(2)}% <small>({result.worst_hook})</small></dd></div>
            <div><dt>Recorded seed count</dt><dd>{result.seeds.toLocaleString()}</dd></div>
            <div><dt>Tested</dt><dd>{result.fuzzed_at}</dd></div>
          </dl>
          <p className="muted">These are results from a test sample, not the chance that your YAML or group will fail. The “default” check uses randomized options, not just the game’s default settings.</p>
        </section>
        <h3>Reading the colours</h3>
        <ul className="fuzzer-meanings">
          <li><strong className="fuzz-pill-clean">Green: clean.</strong> Low failure rates in the recorded checks.</li>
          <li><strong className="fuzz-pill-flaky">Amber: flaky.</strong> Reliability problems were found.</li>
          <li><strong className="fuzz-pill-broken">Red: broken.</strong> Substantial generation problems were found.</li>
        </ul>
        <p>No badge means there is no recorded fuzz result for that version. It does not mean it passed.</p>
        <h3>What should I do with this?</h3>
        <p>Check the version and its setup guide, then test your actual YAMLs together before your session. If generation fails, keep the error log and check the APWorld’s known issues.</p>
        <p>Fuzz results describe generation quality. They are separate from the security audit and do not certify safety, gameplay correctness or compatibility with every multiworld.</p>
      </div>
      <footer className="settings-modal-footer">
        <a className="btn" href="/guides/what-is-the-fuzzer">Read the full fuzzer guide</a>
        <button type="button" className="btn btn-primary" onClick={close}>Got it</button>
      </footer>
    </dialog>, document.body,
  );
}
