import { json } from "@codemirror/lang-json";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useEffect, useState } from "react";

const theme = EditorView.theme({
  "&": { backgroundColor: "var(--surface)", color: "var(--ink)" },
  ".cm-gutters": { backgroundColor: "var(--surface-2)", color: "var(--muted)", border: "none" },
  ".cm-activeLine": { backgroundColor: "transparent" },
  ".cm-activeLineGutter": { backgroundColor: "var(--surface-3)" },
  ".cm-content": { fontFamily: "var(--mono)", caretColor: "var(--ink)" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": { backgroundColor: "var(--accent-wash) !important" },
  ".cm-cursor": { borderLeftColor: "var(--ink)" },
});

function useDark() {
  const q = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setDark(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return dark;
}

export function JsonEditor({
  value,
  onChange,
  asJson,
  minHeight = "120px",
  maxHeight = "360px",
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  asJson: boolean;
  minHeight?: string;
  maxHeight?: string;
  label: string;
}) {
  const dark = useDark();
  return (
    <div className="cm-wrap" aria-label={label}>
      <CodeMirror
        value={value}
        onChange={onChange}
        theme={dark ? "dark" : "light"}
        extensions={[theme, EditorView.lineWrapping, ...(asJson ? [json()] : [])]}
        minHeight={minHeight}
        maxHeight={maxHeight}
        basicSetup={{ lineNumbers: asJson, foldGutter: asJson, highlightActiveLine: false, autocompletion: false }}
      />
    </div>
  );
}
