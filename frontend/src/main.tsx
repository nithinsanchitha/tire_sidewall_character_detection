import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Aperture,
  ArrowUpRight,
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileText,
  Layers,
  LoaderCircle,
  MessageSquare,
  ScanLine,
  Send,
  ShieldCheck,
  StopCircle,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Fields, Scan, Citation, Health, Reply } from "./types";
import "./style.css";
const fieldLabels: Record<keyof Fields, string> = {
  brand: "Brand",
  width_mm: "Width · mm",
  aspect_ratio: "Aspect ratio · %",
  construction: "Construction",
  rim_inches: "Rim diameter · in",
  load_index: "Load index",
  speed_rating: "Speed rating",
  dot_code: "DOT marking",
  manufacture_week: "Manufacturing week",
  manufacture_year: "Manufacturing year",
};
const numeric = new Set([
  "width_mm",
  "aspect_ratio",
  "rim_inches",
  "load_index",
  "manufacture_week",
  "manufacture_year",
]);
function References({ items }: { items: Citation[] }) {
  return (
    <div className="references">
      {items.map((c) => (
        <details key={c.chunk_id}>
          <summary>
            <FileText size={16} />
            <span>
              {c.document}
              {c.page ? ` · p. ${c.page}` : ""}
              <small>{c.chunk_id}</small>
            </span>
            <ArrowUpRight size={15} />
          </summary>
          <p>{c.text}</p>
          <small>
            Cosine similarity: {c.score.toFixed(3)} · retrieval relevance, not
            OCR confidence
          </small>
        </details>
      ))}
    </div>
  );
}
function Viewer({ scan }: { scan: Scan }) {
  const [boxes, setBoxes] = useState(true);
  return (
    <>
      <div className="panel-heading">
        <h3>Annotated image</h3>
        <label className="check">
          <input
            type="checkbox"
            checked={boxes}
            onChange={(e) => setBoxes(e.target.checked)}
          />{" "}
          Show boxes
        </label>
      </div>
      <div className="viewer">
        <img src={scan.image_url} alt="Uploaded tire sidewall" />
        {boxes && (
          <svg
            viewBox={`0 0 ${scan.width} ${scan.height}`}
            aria-label="OCR bounding boxes"
          >
            {scan.detections.map((d, i) => (
              <g key={i}>
                <polygon
                  points={d.polygon.map((p) => p.join(",")).join(" ")}
                  fill="#57e7c522"
                  stroke="#20c998"
                  strokeWidth={Math.max(2, scan.width / 450)}
                />
                <title>
                  {d.text}{" "}
                  {d.confidence !== null
                    ? `${(d.confidence * 100).toFixed(1)}%`
                    : ""}
                </title>
              </g>
            ))}
          </svg>
        )}
      </div>
      <p className="muted tiny">
        Boxes use the original image coordinates, including after crop and
        rotation.
      </p>
    </>
  );
}
function App() {
  const [health, setHealth] = useState<Health | null>(null),
    [healthError, setHealthError] = useState(false);
  const [scans, setScans] = useState<Scan[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState<Scan | null>(null);
  const [fields, setFields] = useState<Fields | null>(null),
    [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false),
    [chatBusy, setChatBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [tab, setTab] = useState<"scan" | "history" | "knowledge">("scan");
  const [rotation, setRotation] = useState("0"),
    [contrast, setContrast] = useState(true),
    [crop, setCrop] = useState("");
  const [question, setQuestion] = useState(""),
    [reply, setReply] = useState<Reply | null>(null),
    [drag, setDrag] = useState(false);
  const [camera, setCamera] = useState(false),
    [devices, setDevices] = useState<MediaDeviceInfo[]>([]),
    [device, setDevice] = useState("");
  const video = useRef<HTMLVideoElement>(null),
    stream = useRef<MediaStream | null>(null),
    cameraToken = useRef(0),
    activeId = useRef<string | null>(null),
    fileInput = useRef<HTMLInputElement>(null);
  const refreshHealth = async () => {
    try {
      setHealth(await api<Health>("/health"));
      setHealthError(false);
    } catch {
      setHealthError(true);
    }
  };
  const history = async (p = page) => {
    const r = await api<{ items: Scan[]; total: number }>(
      `/api/scans?page=${p}&page_size=6`,
    );
    setScans(r.items);
    setTotal(r.total);
  };
  useEffect(() => {
    void refreshHealth();
    void history(1).catch(() => {});
    const timer = setInterval(() => void refreshHealth(), 15000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    void history(page).catch((e) => setError(e.message));
  }, [page]);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (camera && video.current && stream.current) {
      video.current.srcObject = stream.current;
      void video.current.play().catch(() => setError("Camera could not play."));
    }
  }, [camera]);
  useEffect(
    () => () => {
      cameraToken.current++;
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  const stopCamera = () => {
    cameraToken.current++;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setCamera(false);
  };
  const startCamera = async () => {
    stopCamera();
    setError("");
    const token = ++cameraToken.current;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Camera requires localhost or HTTPS and a supported browser. Image upload remains available.",
        );
      const s = await navigator.mediaDevices.getUserMedia({
        video: device
          ? { deviceId: { exact: device } }
          : { facingMode: "environment" },
        audio: false,
      });
      if (token !== cameraToken.current) {
        s.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = s;
      const cameras = (await navigator.mediaDevices.enumerateDevices()).filter(
        (d) => d.kind === "videoinput",
      );
      if (token !== cameraToken.current) {
        s.getTracks().forEach((t) => t.stop());
        return;
      }
      setDevices(cameras);
      setCamera(true);
    } catch (e) {
      if (token === cameraToken.current) {
        stopCamera();
        setError(e instanceof Error ? e.message : "Camera unavailable");
      }
    }
  };
  const choose = (f: File) => {
    setError("");
    setNotice("");
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) {
      setError("Choose JPEG, PNG or WebP.");
      return;
    }
    if (f.size > 12 * 1024 * 1024) {
      setError("Image exceeds 12 MB.");
      return;
    }
    stopCamera();
    setFile(f);
    setSelected(null);
    activeId.current = null;
    setReply(null);
    setCrop("");
  };
  const capture = () => {
    const v = video.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")?.drawImage(v, 0, 0);
    canvas.toBlob((blob) => {
      if (blob)
        choose(new File([blob], "camera-capture.png", { type: "image/png" }));
    }, "image/png");
  };
  const selectScan = (s: Scan) => {
    stopCamera();
    setSelected(s);
    activeId.current = s.id;
    setFields(s.fields);
    setFile(null);
    setReply(null);
    setQuestion("");
    setTab("scan");
    setError("");
    setNotice("");
  };
  const analyze = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("rotation", rotation);
      data.append("contrast", String(contrast));
      if (crop.trim()) data.append("crop", crop);
      const s = await api<Scan>("/api/scans", { method: "POST", body: data });
      selectScan(s);
      await history();
      void refreshHealth();
      setNotice("Scan saved. Review OCR and extracted fields.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    if (!selected || !fields) return;
    setBusy(true);
    setError("");
    try {
      const s = await api<Scan>(`/api/scans/${selected.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      setSelected(s);
      setFields(s.fields);
      setReply(null);
      setNotice("Corrections saved. Future answers use these fields.");
      await history();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (s: Scan) => {
    if (
      !window.confirm("Delete this scan, image, corrections and conversation?")
    )
      return;
    try {
      await api(`/api/scans/${s.id}`, { method: "DELETE" });
      if (selected?.id === s.id) {
        setSelected(null);
        activeId.current = null;
        setFields(null);
      }
      setNotice("Scan deleted.");
      await history();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const ask = async (q = question) => {
    if (!selected || !q.trim()) return;
    const id = selected.id;
    setChatBusy(true);
    setError("");
    try {
      const r = await api<Reply>(`/api/scans/${id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (activeId.current === id) {
        setReply(r);
        setQuestion("");
        const s = await api<Scan>(`/api/scans/${id}`);
        if (activeId.current === id) setSelected(s);
      }
    } catch (e) {
      if (activeId.current === id) setError((e as Error).message);
    } finally {
      setChatBusy(false);
    }
  };
  const ingest = async (f: File) => {
    setBusy(true);
    setError("");
    try {
      const data = new FormData();
      data.append("file", f);
      const r = await api<{ chunks_added: number }>("/api/documents", {
        method: "POST",
        body: data,
      });
      setNotice(`Reference ingested · ${r.chunks_added} new chunks`);
      void refreshHealth();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const size = selected?.fields;
  const sizeText =
    size?.width_mm && size.aspect_ratio && size.rim_inches
      ? `${size.width_mm}/${size.aspect_ratio} ${size.construction === "radial" ? "R" : size.construction === "diagonal" ? "D" : "B"}${size.rim_inches}`
      : "Fields need review";
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#" aria-label="Tire Vision AI home">
          <span className="brand-icon">
            <Aperture size={26} />
          </span>
          <span>
            TIRE VISION<small>AI WORKSPACE</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {(
            [
              ["scan", "Scan workspace", ScanLine],
              ["history", "Scan history", Clock3],
              ["knowledge", "Knowledge base", Layers],
            ] as const
          ).map(([key, label, Icon]) => (
            <button
              className={tab === key ? "nav-item active" : "nav-item"}
              key={key}
              onClick={() => {
                stopCamera();
                setTab(key);
              }}
            >
              <Icon size={19} />
              {label}
              {key === "history" && <span className="count">{total}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={22} />
          <strong>Local by design</strong>
          <p>
            Images and scans stay in your backend. Ollama runs on your machine.
          </p>
          <span className="version">TIRE VISION AI / v1.0</span>
        </div>
      </aside>
      <div className="main">
        <header>
          <span className="breadcrumb">
            Workspace <span>/</span>{" "}
            {tab === "history"
              ? "Scan history"
              : tab === "knowledge"
                ? "Knowledge base"
                : "Image analysis"}
          </span>
          <div className="local-badge">
            <span className="dot" />{" "}
            {health?.provider === "external"
              ? "External LLM configured"
              : "Local inference"}
          </div>
        </header>
        <main>
          <div className="page-title">
            <div className="eyebrow">SIDEWALL INTELLIGENCE</div>
            <h1>
              {tab === "history"
                ? "Your scan history"
                : tab === "knowledge"
                  ? "Grounded in references"
                  : "Read the details. Understand the tire."}
            </h1>
            <p>
              Extract sidewall markings, review the results, and explore the
              reference behind every explanation.
            </p>
          </div>
          <div className="statuses">
            {[
              ["OCR model", health?.ocr],
              ["Reference index", health?.retrieval],
              ["Language model", health?.llm],
            ].map(([label, status]) => {
              const s = status as Health["ocr"] | undefined;
              return (
                <div key={label as string} className="status">
                  <span className={`dot ${s?.ready ? "" : "pending"}`} />
                  <span>{label as string}</span>
                  <small title={s?.detail}>
                    {healthError
                      ? "Backend offline"
                      : s?.ready
                        ? "Ready"
                        : "Setup / idle"}
                  </small>
                </div>
              );
            })}
          </div>
          {error && (
            <div className="alert error" role="alert">
              <span>{error}</span>
              <button
                className="icon"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={18} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={18} />
              {notice}
            </div>
          )}
          {tab === "knowledge" ? (
            <section className="panel">
              <div className="panel-heading">
                <h2>Reference library</h2>
                <Layers size={22} />
              </div>
              <p>
                Add reference documents to the shared local knowledge base. PDF
                pages and chunk identifiers are preserved. Documents are treated
                as evidence, never as instructions.
              </p>
              <label className="dropzone small">
                <FileText size={32} />
                <strong>Ingest a PDF or TXT reference</strong>
                <span>UTF-8 text or unencrypted text PDF · up to 12 MB</span>
                <input
                  type="file"
                  accept=".pdf,.txt"
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void ingest(f);
                    e.target.value = "";
                  }}
                />
              </label>
              <p className="muted">
                The bundled notes are project-authored and link to NHTSA
                TireWise for further reading. Only upload material you have
                permission to use. An embedding model must be installed for
                ingestion.
              </p>
              <div className="setup-note">
                <strong>Service details</strong>
                {health && (
                  <ul>
                    <li>{health.ocr.detail}</li>
                    <li>{health.retrieval.detail}</li>
                    <li>{health.llm.detail}</li>
                  </ul>
                )}
              </div>
            </section>
          ) : tab === "history" ? (
            <section className="panel">
              <div className="panel-heading">
                <h2>
                  Saved scans <span className="pill">{total}</span>
                </h2>
                <button onClick={() => void history()}>Refresh</button>
              </div>
              {scans.length === 0 ? (
                <div className="empty">
                  <Clock3 size={35} />
                  <h3>No scans yet</h3>
                  <p>Analyze an uploaded image to start your history.</p>
                  <button className="primary" onClick={() => setTab("scan")}>
                    Create a scan
                  </button>
                </div>
              ) : (
                <div className="history-grid">
                  {scans.map((s) => (
                    <article className="history-card" key={s.id}>
                      <button
                        className="history-image"
                        onClick={() => selectScan(s)}
                      >
                        <img src={s.image_url} alt={s.filename} />
                      </button>
                      <div>
                        <strong>
                          {s.fields.brand || "Unidentified brand"}
                        </strong>
                        <p>{s.filename}</p>
                        <small>
                          {new Date(s.created_at).toLocaleString()} ·{" "}
                          {s.detections.length} text regions
                        </small>
                        <div className="row">
                          <button
                            onClick={() =>
                              void api<Scan>(`/api/scans/${s.id}`)
                                .then(selectScan)
                                .catch((e) => setError(e.message))
                            }
                          >
                            Open scan <ArrowUpRight size={14} />
                          </button>
                          <button
                            className="icon danger"
                            onClick={() => void remove(s)}
                            aria-label={`Delete ${s.filename}`}
                          >
                            <Trash2 size={17} />
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              <div className="pagination">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft size={16} />
                  Previous
                </button>
                <span>
                  Page {page} of {Math.max(1, Math.ceil(total / 6))}
                </span>
                <button
                  disabled={page * 6 >= total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                  <ChevronRight size={16} />
                </button>
              </div>
            </section>
          ) : (
            <>
              <div className="workspace-grid">
                <section className="panel input-panel">
                  <div className="panel-heading">
                    <h2>
                      <span className="step">01</span> Image input
                    </h2>
                    <span className="pill">UPLOAD FIRST</span>
                  </div>
                  {selected ? (
                    <>
                      <Viewer scan={selected} />
                      <button
                        className="wide"
                        onClick={() => {
                          setSelected(null);
                          activeId.current = null;
                          setFile(null);
                          setReply(null);
                        }}
                      >
                        <Upload size={17} /> Analyze another image
                      </button>
                    </>
                  ) : (
                    <>
                      {camera ? (
                        <div className="camera">
                          <video ref={video} autoPlay muted playsInline />
                          <div className="row">
                            <button className="primary" onClick={capture}>
                              <Camera size={17} />
                              Capture
                            </button>
                            <button onClick={stopCamera}>
                              <StopCircle size={17} />
                              Stop Camera
                            </button>
                          </div>
                        </div>
                      ) : preview ? (
                        <div className="preview">
                          <img src={preview} alt="Selected image preview" />
                          <div className="row">
                            <span className="truncate">{file?.name}</span>
                            <button onClick={() => setFile(null)}>
                              Remove
                            </button>
                            <button onClick={() => void startCamera()}>
                              Retake
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          className={`dropzone ${drag ? "drag" : ""}`}
                          onDragOver={(e) => {
                            e.preventDefault();
                            setDrag(true);
                          }}
                          onDragLeave={() => setDrag(false)}
                          onDrop={(e) => {
                            e.preventDefault();
                            setDrag(false);
                            const f = e.dataTransfer.files[0];
                            if (f) choose(f);
                          }}
                        >
                          <div className="upload-icon">
                            <Upload size={30} />
                          </div>
                          <h3>Drop your tire image here</h3>
                          <p>Clear, close-up sidewall photos work best.</p>
                          <button onClick={() => fileInput.current?.click()}>
                            Choose image <ArrowUpRight size={16} />
                          </button>
                          <span>JPEG, PNG or WebP · up to 12 MB</span>
                        </div>
                      )}
                      <input
                        ref={fileInput}
                        className="hidden"
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) choose(f);
                          e.target.value = "";
                        }}
                      />
                      <div className="or">
                        <span />
                        or use a camera
                        <span />
                      </div>
                      <div className="row">
                        <button
                          className="wide"
                          disabled={camera}
                          onClick={() => void startCamera()}
                        >
                          <Camera size={17} />
                          Start Camera
                        </button>
                        {devices.length > 0 && (
                          <select
                            aria-label="Camera selection"
                            value={device}
                            disabled={camera}
                            onChange={(e) => setDevice(e.target.value)}
                          >
                            <option value="">Default camera</option>
                            {devices.map((d, i) => (
                              <option key={d.deviceId} value={d.deviceId}>
                                {d.label || `Camera ${i + 1}`}
                              </option>
                            ))}
                          </select>
                        )}
                      </div>
                      <p className="muted tiny">
                        Camera is optional. Access is requested only when
                        started; localhost or HTTPS is required.
                      </p>
                      <details className="preprocessing">
                        <summary>Preprocessing options</summary>
                        <div className="form-row">
                          <label>
                            Rotate clockwise
                            <select
                              value={rotation}
                              onChange={(e) => setRotation(e.target.value)}
                            >
                              {["0", "90", "180", "270"].map((v) => (
                                <option key={v} value={v}>
                                  {v}°
                                </option>
                              ))}
                            </select>
                          </label>
                          <label className="check">
                            <input
                              type="checkbox"
                              checked={contrast}
                              onChange={(e) => setContrast(e.target.checked)}
                            />
                            Enhance contrast
                          </label>
                        </div>
                        <label>
                          Crop in original pixels
                          <input
                            value={crop}
                            onChange={(e) => setCrop(e.target.value)}
                            placeholder="[x, y, width, height]"
                          />
                          <small>
                            Leave blank for the full image. Coordinates refer to
                            pixels before rotation.
                          </small>
                        </label>
                      </details>
                      <button
                        className="primary wide analyze"
                        disabled={!file || busy}
                        onClick={() => void analyze()}
                      >
                        {busy ? (
                          <LoaderCircle className="spin" size={19} />
                        ) : (
                          <ScanLine size={19} />
                        )}{" "}
                        {busy ? "Reading sidewall…" : "Analyze image"}
                        <ArrowUpRight size={18} />
                      </button>
                    </>
                  )}
                </section>
                <section className="panel results-panel">
                  <div className="panel-heading">
                    <h2>
                      <span className="step">02</span> Tire information
                    </h2>
                    <span className="pill">
                      {selected ? "REVIEW REQUIRED" : "AWAITING IMAGE"}
                    </span>
                  </div>
                  {selected && fields ? (
                    <>
                      <div className="tire-summary">
                        <span className="eyebrow">
                          {selected.fields.brand || "BRAND NOT IDENTIFIED"}
                        </span>
                        <h2>{sizeText}</h2>
                        <p>
                          {selected.detections.length} recognized text regions ·{" "}
                          {selected.correction_count} saved corrections
                        </p>
                      </div>
                      <div className="fields">
                        {(Object.keys(fieldLabels) as (keyof Fields)[]).map(
                          (key) => (
                            <label key={key}>
                              {fieldLabels[key]}
                              {key === "construction" ? (
                                <select
                                  value={fields[key] ?? ""}
                                  onChange={(e) =>
                                    setFields({
                                      ...fields,
                                      construction: (e.target.value ||
                                        null) as Fields["construction"],
                                    })
                                  }
                                >
                                  <option value="">Not identified</option>
                                  {["radial", "diagonal", "belted"].map((v) => (
                                    <option key={v}>{v}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={numeric.has(key) ? "number" : "text"}
                                  value={fields[key] ?? ""}
                                  placeholder="Not identified"
                                  onChange={(e) =>
                                    setFields({
                                      ...fields,
                                      [key]:
                                        e.target.value === ""
                                          ? null
                                          : numeric.has(key)
                                            ? Number(e.target.value)
                                            : e.target.value,
                                    })
                                  }
                                />
                              )}
                            </label>
                          ),
                        )}
                      </div>
                      <button
                        className="wide"
                        disabled={busy}
                        onClick={() => void save()}
                      >
                        <Check size={17} />
                        Save corrections
                      </button>
                      <details className="warnings">
                        <summary>Extraction notes & original fields</summary>
                        {selected.parse_warnings.map((w, i) => (
                          <p key={i}>{w}</p>
                        ))}
                        <pre>
                          {JSON.stringify(selected.original_fields, null, 2)}
                        </pre>
                      </details>
                    </>
                  ) : (
                    <div className="empty result-empty">
                      <div className="scan-art">
                        <ScanLine size={42} />
                      </div>
                      <h3>The details are in the sidewall.</h3>
                      <p>
                        Upload a photo to extract tire size, service markings,
                        brand and a supported DOT date code.
                      </p>
                      <div className="empty-fields">
                        <span>
                          Width <b>—</b>
                        </span>
                        <span>
                          Load index <b>—</b>
                        </span>
                        <span>
                          Speed rating <b>—</b>
                        </span>
                        <span>
                          Date code <b>—</b>
                        </span>
                      </div>
                      <div className="tip">
                        <ShieldCheck size={20} />
                        <p>
                          Recognition reads the image. Reference retrieval helps
                          explain what the markings mean.
                        </p>
                      </div>
                    </div>
                  )}
                </section>
              </div>
              {selected && (
                <section className="panel raw">
                  <div className="panel-heading">
                    <h2>Recognized text</h2>
                    <span className="pill">ORIGINAL OCR</span>
                  </div>
                  {selected.detections.length ? (
                    <div className="ocr-list">
                      {selected.detections.map((d, i) => (
                        <div key={i}>
                          <span>{d.text}</span>
                          <span>
                            {d.confidence === null
                              ? "No confidence provided"
                              : `${(d.confidence * 100).toFixed(1)}% OCR score`}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>
                      No visible text was recognized. Try a closer, sharper
                      image or different preprocessing.
                    </p>
                  )}
                  <p className="muted tiny">
                    EasyOCR recognizer scores are uncalibrated for tire images.
                    Editing fields never changes these results.
                  </p>
                </section>
              )}
              <section className="panel knowledge-panel">
                <div className="panel-heading">
                  <h2>
                    <span className="step">03</span> Understand the markings
                  </h2>
                  <span className="pill">
                    <MessageSquare size={13} /> GROUNDED ANSWERS
                  </span>
                </div>
                <div className="knowledge-grid">
                  <div>
                    <h3>Reference evidence</h3>
                    <p className="muted">
                      Answers use retrieved documents and the selected scan’s
                      current fields.
                    </p>
                    {selected?.retrieval_warning && (
                      <p className="alert error">
                        {selected.retrieval_warning}
                      </p>
                    )}
                    {selected?.references.length ? (
                      <References items={selected.references} />
                    ) : (
                      <div className="evidence-empty">
                        <FileText size={24} />
                        <p>
                          {selected
                            ? "No matching reference excerpts available. Check the index or add relevant documents."
                            : "Reference excerpts appear after analysis."}
                        </p>
                      </div>
                    )}
                    <p className="tiny muted">
                      Text alone cannot establish tire condition, vehicle
                      fitment or overall safety.
                    </p>
                  </div>
                  <div className="chat">
                    <div className="chat-top">
                      <span
                        className={`dot ${health?.llm.ready ? "" : "pending"}`}
                      />
                      <strong>Scan assistant</strong>
                      <span>
                        {health?.llm.ready
                          ? "LLM ready"
                          : "LLM offline / setup"}
                      </span>
                    </div>
                    {selected ? (
                      <>
                        <div className="chat-messages" aria-live="polite">
                          {selected.messages.length === 0 ? (
                            <p className="muted">
                              Ask about this scan. If Ollama is offline,
                              retrieved excerpts remain available.
                            </p>
                          ) : (
                            selected.messages.map((m, i) => (
                              <div key={i} className={`message ${m.role}`}>
                                <small>
                                  {m.role === "user" ? "YOU" : "TIRE VISION"}
                                </small>
                                <p>{m.content}</p>
                              </div>
                            ))
                          )}
                          {chatBusy && (
                            <p>
                              <LoaderCircle size={16} className="spin" />{" "}
                              Retrieving and generating…
                            </p>
                          )}
                        </div>
                        {reply?.warning && (
                          <p className="muted tiny">{reply.warning}</p>
                        )}
                        {reply?.citations.length ? (
                          <details className="chat-sources">
                            <summary>
                              {reply.generated
                                ? "Answer citations"
                                : "Retrieved excerpts"}{" "}
                              ({reply.citations.length})
                            </summary>
                            <References items={reply.citations} />
                          </details>
                        ) : null}
                        <button
                          disabled={chatBusy}
                          className="explain"
                          onClick={() =>
                            void ask(
                              "Explain the identified tire markings and state what is missing.",
                            )
                          }
                        >
                          Explain this scan <ArrowUpRight size={14} />
                        </button>
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            void ask();
                          }}
                          className="chat-input"
                        >
                          <input
                            aria-label="Question about selected scan"
                            maxLength={2000}
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            placeholder="What does the size marking mean?"
                          />
                          <button
                            className="primary icon"
                            disabled={chatBusy || !question.trim()}
                            aria-label="Send question"
                          >
                            <Send size={18} />
                          </button>
                        </form>
                      </>
                    ) : (
                      <div className="empty chat-empty">
                        <MessageSquare size={27} />
                        <p>Select a scan to start a conversation.</p>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </>
          )}
          <footer>
            <span>Tire Vision AI</span>
            <span>
              Vision → structured markings → retrieved evidence → explanation
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
