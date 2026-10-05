# Validation report

Performed during implementation, 5 October 2026. This report separates real inference from isolated tests.

| Check | Result | Scope |
|---|---|---|
| Backend isolated tests | Passed, 13 tests | Upload MIME/signature/size, invalid input, CORS, parsing, image decoding, SQLite restart persistence, corrections, scan isolation, pagination, deletion, PDF/TXT extraction, FAISS search with an injected embedding double, offline generation, citation-ID rejection, follow-up context and revision isolation |
| Actual OCR | Passed | Downloaded CRAFT detector and English generation-2 recognizer on the clearly labeled synthetic text image. Recognized `205/55 R16 91V` and `DOT ABCD EF 2323`. No real-tire accuracy claim. |
| Actual embeddings and retrieval | Passed | Downloaded all-MiniLM-L6-v2, normalized embeddings and real FAISS retrieval against project-authored tire notes; actual API TXT/PDF ingestion and page-aware retrieval |
| API integration | Passed | Real image -> OCR -> parser -> reference retrieval -> persistence -> correction -> history -> offline generation -> deletion |
| Box coordinates | Passed | Independent marker-position tests after crop and rotations 0/90/180/270; integration verifies box bounds; viewer inspected with real OCR overlays |
| Browser integration | Passed, 3 tests | Actual multipart UI-to-API transfer, preview, real OCR results, editable fields, persistence, retrieved excerpts with Ollama offline, history, deletion and real document upload |
| Responsive layout | Passed at tested viewports | Desktop 1280x720 and mobile 390x844; mobile document width does not exceed viewport; screenshots visually inspected |
| Camera denial | Passed with simulated denial | Upload still enabled after denied getUserMedia; this is not a physical capture test |
| TypeScript and frontend production build | Passed | `npm run check` and `npm run build` |
| Citation-backed live Ollama answer | Not performed | Ollama/model service was not installed/running. Structured-response citation validation tested with an explicit provider double. |
| Physical camera capture / selection | Not performed | No camera hardware available |
| Docker execution | Not performed | Docker executable unavailable in this environment; Compose/Dockerfiles included for local use |
| Real tire photograph evaluation | Not performed | No licensed unannotated tire photo obtained; references to candidate sources and adding photos are documented |
| External LLM API | Not performed | No key supplied or required for default local mode |
| GitHub Actions on GitHub | Passed | Backend tests and frontend type checks/production build passed in [run 37334046823](https://github.com/nithinsanchitha/tire_sidewall_character_detection/actions/runs/37334046823) for application commit `a11c4d784714a94b4c9d76b729c8edb6346beee7`. |

Early environment dependency installation and initial browser/model download attempts encountered compatibility/download errors. Dependencies were pinned, actual imports verified (torch 2.6.0, torchvision 0.21.0, transformers 4.51.3, sentence-transformers 4.1.0), model downloads completed, and final inference/browser checks passed. Initial checks before dependencies were fully installed failed with an honest setup error rather than substitute detections.

Screenshots `workspace-desktop.png`, `scan-desktop.png`, and `scan-mobile.png` are captured from the actual application. The scan screenshot uses the synthetic target and intentionally saves a TOYO correction while preserving original MICHELIN OCR.
