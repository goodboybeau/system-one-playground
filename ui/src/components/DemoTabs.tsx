import { useEffect, useRef, useState } from "react";

import type { Preset } from "../api";
import type { Demo } from "../lib/demos";

type Props = {
  demos: Demo[];
  active: string;
  running: Set<string>;
  presets: Preset[];
  closed: Demo | null;
  onSelect: (id: string) => void;
  onRename: (id: string, name: string) => void;
  onClose: (id: string) => void;
  onUndoClose: () => void;
  onNewBlank: () => void;
  onDuplicate: () => void;
  onNewFromPreset: (p: Preset) => void;
};

export function DemoTabs(p: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const activeRef = useRef<HTMLDivElement>(null);
  const addRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [p.active]);

  return (
    <div className="demo-bar">
      <div className="demo-tabs" role="tablist" aria-label="Demos">
        {p.demos.map((d) => {
          const on = d.id === p.active;
          return (
            <div key={d.id} ref={on ? activeRef : undefined} className={`demo-tab${on ? " on" : ""}`} data-demo={d.name}>
              {editing === d.id ? (
                <RenameInput
                  initial={d.name}
                  onDone={(name) => {
                    if (name !== null) p.onRename(d.id, name);
                    setEditing(null);
                  }}
                />
              ) : (
                <button
                  role="tab"
                  aria-selected={on}
                  className="demo-tab-name"
                  title="Double-click to rename"
                  onClick={() => p.onSelect(d.id)}
                  onDoubleClick={() => setEditing(d.id)}
                >
                  {p.running.has(d.id) && <i className="demo-busy" aria-label="running" />}
                  {d.name}
                </button>
              )}
              {p.demos.length > 1 && editing !== d.id && (
                <button className="demo-tab-close" aria-label={`Close ${d.name}`} title="Close" onClick={() => p.onClose(d.id)}>
                  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
                    <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
        <div className="demo-new">
          <button ref={addRef} className="demo-add" aria-label="New demo" aria-haspopup="menu" aria-expanded={menu} title="New demo" onClick={() => setMenu((m) => !m)}>
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
              <path d="M6 1.5v9M1.5 6h9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
          {menu && (
            <NewMenu
              anchor={addRef.current!.getBoundingClientRect()}
              presets={p.presets}
              onClose={() => setMenu(false)}
              onBlank={() => {
                setMenu(false);
                p.onNewBlank();
              }}
              onDuplicate={() => {
                setMenu(false);
                p.onDuplicate();
              }}
              onPreset={(preset) => {
                setMenu(false);
                p.onNewFromPreset(preset);
              }}
            />
          )}
        </div>
      </div>
      {p.closed && (
        <div className="demo-undo" role="status">
          Closed “{p.closed.name}”
          <button className="btn ghost sm" onClick={p.onUndoClose}>
            Undo
          </button>
        </div>
      )}
    </div>
  );
}

function RenameInput({ initial, onDone }: { initial: string; onDone: (name: string | null) => void }) {
  const [value, setValue] = useState(initial);
  const done = useRef(false);
  const finish = (name: string | null) => {
    if (done.current) return;
    done.current = true;
    onDone(name);
  };
  return (
    <input
      className="demo-rename"
      aria-label="Demo name"
      autoFocus
      value={value}
      maxLength={60}
      size={Math.max(6, value.length + 1)}
      onFocus={(e) => e.currentTarget.select()}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => finish(value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") finish(value);
        if (e.key === "Escape") finish(null);
      }}
    />
  );
}

function NewMenu({
  anchor,
  presets,
  onClose,
  onBlank,
  onDuplicate,
  onPreset,
}: {
  anchor: DOMRect;
  presets: Preset[];
  onClose: () => void;
  onBlank: () => void;
  onDuplicate: () => void;
  onPreset: (p: Preset) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.parentElement!.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onMove = (e: Event) => {
      if (!(e.target instanceof Node && ref.current?.contains(e.target))) onClose();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    ref.current?.querySelector<HTMLButtonElement>("button")?.focus({ preventScroll: true });
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [onClose]);
  return (
    <div className="menu" role="menu" ref={ref} style={{ top: anchor.bottom + 6, left: Math.max(8, Math.min(anchor.left, window.innerWidth - 250)) }}>
      <button role="menuitem" onClick={onBlank}>
        Blank demo
      </button>
      <button role="menuitem" onClick={onDuplicate}>
        Duplicate this demo
      </button>
      {presets.length > 0 && <div className="menu-label">From a preset</div>}
      {presets.map((p) => (
        <button role="menuitem" key={p.id} onClick={() => onPreset(p)} title={p.description}>
          {p.title}
        </button>
      ))}
    </div>
  );
}
