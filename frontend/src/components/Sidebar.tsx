import {
  BarChart3,
  Braces,
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  LayoutDashboard,
  Layers3,
  Link2,
  Menu,
  Plus,
  Settings2,
  SquareCode,
  Unplug,
  X,
} from "lucide-react";
import type { View } from "../types/document";
import { useEffect, useState } from "react";

const groups = [
  {
    title: "WORKSPACE",
    items: [
      { view: "overview", label: "Overview", icon: LayoutDashboard },
      { view: "document", label: "Documents", icon: FileText },
      { view: "structured", label: "Structured", icon: Layers3 },
    ],
  },
  {
    title: "OUTPUT",
    items: [
      { view: "markdown", label: "Markdown", icon: SquareCode },
      { view: "json", label: "JSON", icon: Braces },
    ],
  },
  {
    title: "INSIGHTS",
    items: [{ view: "analytics", label: "Analytics", icon: BarChart3 }],
  },
] as const;

export function Sidebar({
  view,
  navigate,
}: {
  view: View;
  navigate: (view: View) => void;
}) {
  const [open, setOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobile, setMobile] = useState(
    () => window.matchMedia("(max-width: 760px)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(max-width: 760px)");
    const update = () => setMobile(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!open || !mobile) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open, mobile]);
  const go = (next: View) => {
    navigate(next);
    setOpen(false);
  };
  return (
    <>
      <button
        className="mobile-menu icon-button"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Close navigation" : "Open navigation"}
        aria-expanded={open}
        aria-controls="workspace-navigation-panel"
      >
        {open ? <X /> : <Menu />}
      </button>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={`sidebar ${open ? "is-open" : ""}`}
        id="workspace-navigation-panel"
        inert={mobile && !open}
        aria-hidden={mobile && !open}
      >
        <a className="brand" href="#/overview" onClick={() => setOpen(false)}>
          <img src="/logo.svg" alt="" />
          <span>
            STRUCTURA<span className="wordmark-dot">.</span>
          </span>
        </a>
        <div className="workspace-selector-wrap">
          <button
            className="workspace-select"
            onClick={() => setWorkspaceOpen(!workspaceOpen)}
            aria-expanded={workspaceOpen}
            aria-label="Select workspace"
          >
            <span className="workspace-avatar">S</span>
            <span>
              <strong>Demo workspace</strong>
              <small>Personal workspace</small>
            </span>
            <ChevronDown size={14} />
          </button>
          {workspaceOpen && (
            <div className="workspace-popover">
              <button onClick={() => setWorkspaceOpen(false)}>
                <Check size={13} />
                Demo workspace<span>MOCK</span>
              </button>
              <p>This frontend demo contains one workspace.</p>
            </div>
          )}
        </div>
        <button
          className="button primary sidebar-upload"
          onClick={() => go("upload")}
        >
          <Plus size={16} />
          Upload document
        </button>
        <nav aria-label="Main navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-label">{group.title}</div>
              {group.items.map(({ view: item, label, icon: Icon }) => (
                <a
                  href={`#/${item}`}
                  key={item}
                  onClick={() => setOpen(false)}
                  className={`nav-item ${view === item ? "active" : ""}`}
                  aria-current={view === item ? "page" : undefined}
                >
                  <Icon size={17} />
                  <span>{label}</span>
                  {item === "document" && <small aria-hidden="true">1</small>}
                  {view === item && <span className="nav-active-dot" />}
                </a>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="source-promise">
            <Link2 size={15} />
            <strong>Every result. Its exact source.</strong>
            <span>POWERED BY TRACEBACK</span>
          </div>
          <div className="connection-status">
            <div>
              <Unplug size={13} />
              <span>Backend not connected</span>
            </div>
            <span>
              <span className="demo-dot" />
              MOCK MODE<code>v0.1</code>
            </span>
          </div>
          <div className="profile-area">
            <button
              className="profile-button"
              onClick={() => setSettingsOpen(!settingsOpen)}
              aria-expanded={settingsOpen}
              aria-label="Workspace settings"
            >
              <span className="profile-avatar">S</span>
              <span>
                <strong>Demo account</strong>
                <small>Local frontend</small>
              </span>
              <Settings2 size={15} />
            </button>
            {settingsOpen && (
              <div className="settings-popover">
                <strong>Workspace settings</strong>
                <p>
                  Mock-only frontend. No backend connection or account settings
                  are configured.
                </p>
                <button
                  onClick={() => {
                    setSettingsOpen(false);
                    go("upload");
                  }}
                >
                  Explore upload workflow
                  <ChevronRight size={13} />
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
