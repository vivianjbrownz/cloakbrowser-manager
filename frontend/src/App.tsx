import { useState, useCallback, useEffect } from "react";
import { Bot, Lock, Microscope, PanelLeftClose, PanelLeft, Table2 } from "lucide-react";
import { useProfiles } from "./hooks/useProfiles";
import { api, setOnUnauthorized, type ProfileCreateData } from "./lib/api";
import { ProfileList } from "./components/ProfileList";
import { ProfileForm } from "./components/ProfileForm";
import { ProfileViewer } from "./components/ProfileViewer";
import { LaunchButton } from "./components/LaunchButton";
import { StatusIndicator } from "./components/StatusIndicator";
import { LoginPage } from "./components/LoginPage";
import { InventoryTable } from "./components/InventoryTable";
import { ThemeToggle } from "./components/ThemeToggle";
import { RunningProfilesBar } from "./components/RunningProfilesBar";
import { RegistrationLinksIcon, RegistrationLinksPlugin } from "./components/RegistrationLinksPlugin";
import { ResearchCenter } from "./components/ResearchCenter";

type AuthState = "checking" | "required" | "ok" | "error";
type View = "inventory" | "registration" | "research" | "empty" | "create" | "edit" | "view";

export default function App() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [authRequired, setAuthRequired] = useState(false);
  const [scopedMode, setScopedMode] = useState(false);

  useEffect(() => {
    setOnUnauthorized(() => setAuthState("required"));

    api.authStatus()
      .then(({ auth_required, authenticated, role }) => {
        setAuthRequired(auth_required);
        setScopedMode(role === "scoped");
        if (!auth_required || authenticated) {
          setAuthState("ok");
        } else {
          setAuthState("required");
        }
      })
      .catch((err) => {
        console.warn("[auth] status check failed:", err);
        setAuthState("error");
      });

    return () => setOnUnauthorized(null);
  }, []);

  if (authState === "checking") {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  if (authState === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-0">
        <div className="text-center">
          <p className="text-red-400 text-sm mb-2">Unable to reach the server</p>
          <button
            onClick={() => {
              setAuthState("checking");
              api.authStatus()
                .then(({ auth_required, authenticated }) => {
                  setAuthRequired(auth_required);
                  setAuthState(!auth_required || authenticated ? "ok" : "required");
                })
                .catch(() => setAuthState("error"));
            }}
            className="text-xs text-gray-400 hover:text-gray-200 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (authState === "required") {
    return <LoginPage onSuccess={() => setAuthState("ok")} />;
  }

  return (
    <AppContent
      authRequired={authRequired}
      scopedMode={scopedMode}
      onLogout={async () => {
        await api.logout();
        setAuthState("required");
      }}
    />
  );
}

interface AppContentProps {
  authRequired: boolean;
  scopedMode: boolean;
  onLogout: () => void;
}

function AppContent({ authRequired, scopedMode, onLogout }: AppContentProps) {
  const { profiles, loading, error, refresh, create, update, remove, archive, restore, launch, stop } = useProfiles();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("inventory");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const selected = profiles.find((p) => p.id === selectedId) ?? null;

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    const profile = profiles.find((p) => p.id === id);
    setView(profile?.status === "running" && !profile.is_archived ? "view" : "edit");
  }, [profiles]);

  const handleNew = useCallback(() => {
    setSelectedId(null);
    setView("create");
  }, []);

  const handleCreate = useCallback(async (data: ProfileCreateData) => {
    const profile = await create(data);
    if (profile) {
      setSelectedId(profile.id);
      setView("edit");
    }
  }, [create]);

  const handleUpdate = useCallback(async (data: ProfileCreateData) => {
    if (!selectedId) return;
    await update(selectedId, data);
  }, [selectedId, update]);

  const handleDelete = useCallback(async () => {
    if (!selectedId) return;
    await remove(selectedId);
    setSelectedId(null);
    setView("inventory");
  }, [selectedId, remove]);

  const handleArchiveProfile = useCallback(async (profileId: string) => {
    const profile = await archive(profileId);
    if (profile) {
      setSelectedId(profileId);
      setView("inventory");
    }
  }, [archive]);

  const handleRestoreProfile = useCallback(async (profileId: string) => {
    const profile = await restore(profileId);
    if (profile) {
      setSelectedId(profileId);
      setView("edit");
    }
  }, [restore]);

  const handleLaunchProfile = useCallback(async (profileId: string) => {
    const profile = profiles.find((p) => p.id === profileId);
    if (profile?.is_archived) return;
    const result = await launch(profileId);
    if (result) setView("view");
    setSelectedId(profileId);
  }, [launch, profiles]);

  const handleStopProfile = useCallback(async (profileId: string) => {
    await stop(profileId);
    setSelectedId(profileId);
    setView("edit");
  }, [stop]);

  const handleLaunch = useCallback(async () => {
    if (!selectedId) return;
    await handleLaunchProfile(selectedId);
  }, [handleLaunchProfile, selectedId]);

  const handleStop = useCallback(async () => {
    if (!selectedId) return;
    await handleStopProfile(selectedId);
  }, [handleStopProfile, selectedId]);

  const handleVncDisconnect = useCallback(() => {
    setView("edit");
  }, []);

  const handleStartUi = useCallback(async (profileId: string) => {
    await api.startProfileUi(profileId);
    await refresh();
  }, [refresh]);

  const handleStopUi = useCallback(async (profileId: string) => {
    await api.stopProfileUi(profileId);
    await refresh();
  }, [refresh]);

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading...</div>
      </div>
    );
  }

  if (scopedMode) {
    const assigned = profiles[0] ?? null;
    return (
      <div className="h-screen flex flex-col bg-surface-0">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-accent" />
            <span className="text-sm font-semibold">AgentOS Browser</span>
            {assigned && <span className="text-xs text-gray-500">{assigned.name}</span>}
          </div>
          <div className="flex items-center gap-2">
            {assigned && !assigned.is_archived && !assigned.headless && assigned.status === "running" && (
              <button onClick={() => handleStopUi(assigned.id)} className="rounded bg-surface-2 px-3 py-1.5 text-xs text-gray-200 hover:bg-surface-3">
                关闭 UI，返回 Agent
              </button>
            )}
            <ThemeToggle />
          </div>
        </div>
        <div className="px-4 py-2 text-xs text-cyan-200 bg-cyan-950/40 border-b border-cyan-900/60">
          这里始终是分配给你的独立浏览器。打开此页面进行人工接管时，请让 AgentOS 暂停浏览器操作；完成后在对话中让它继续。
        </div>
        {error && <div className="px-4 py-2 text-sm text-red-400">{error}</div>}
        <div className="flex-1 min-h-0">
          {!assigned && (
            <div className="h-full flex items-center justify-center text-sm text-gray-500">No browser profile is assigned.</div>
          )}
          {assigned && (assigned.status === "stopped" || assigned.headless) && (
            <div className="h-full flex flex-col gap-4 items-center justify-center">
              <p className="text-sm text-gray-400">
                {assigned.status === "running" ? "Agent 正在无头模式操作；打开 UI 会保留资料并切换到可视模式。" : "浏览器当前未运行；打开 UI 后才启用图形界面。"}
              </p>
              <button onClick={() => handleStartUi(assigned.id)} className="rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90">
                打开浏览器 UI
              </button>
            </div>
          )}
          {assigned && assigned.status === "running" && !assigned.headless && (
            <ProfileViewer
              key={assigned.id}
              profileId={assigned.id}
              cdpUrl={null}
              clipboardSync={assigned.clipboard_sync}
              onDisconnect={refresh}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r border-border bg-surface-1 flex-shrink-0">
          <ProfileList
            profiles={profiles}
            selectedId={selectedId}
            onSelect={handleSelect}
            onNew={handleNew}
          />
        </div>
      )}

      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-1">
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setSelectedId(null);
                setView("inventory");
              }}
              className={`text-gray-500 hover:text-gray-300 p-1 ${view === "inventory" ? "text-accent" : ""}`}
              title="Inventory"
            >
              <Table2 className="h-4 w-4" />
            </button>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="text-gray-500 hover:text-gray-300 p-1"
              title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </button>
            <button
              onClick={() => {
                setSelectedId(null);
                setView("registration");
              }}
              className={`text-gray-500 hover:text-gray-300 p-1 ${view === "registration" ? "text-accent" : ""}`}
              title="Registration links"
            >
              <RegistrationLinksIcon />
            </button>
            <button
              onClick={() => {
                setSelectedId(null);
                setView("research");
              }}
              className={`text-gray-500 hover:text-gray-300 p-1 ${view === "research" ? "text-accent" : ""}`}
              title="Research Center"
            >
              <Microscope className="h-4 w-4" />
            </button>
            {selected && (
              <div className="flex items-center gap-2">
                <StatusIndicator status={selected.status} size="md" />
                <span className="text-sm font-medium">{selected.name}</span>
                <span className="text-xs text-gray-500 capitalize">{selected.platform}</span>
                {selected.is_archived && (
                  <span className="text-[10px] uppercase tracking-wide text-gray-500 border border-border rounded-full px-2 py-0.5">
                    Archived
                  </span>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {selected && !selected.is_archived && (
              <LaunchButton
                status={selected.status}
                onLaunch={handleLaunch}
                onStop={handleStop}
              />
            )}
            <ThemeToggle />
            {authRequired && (
              <button
                onClick={onLogout}
                className="text-gray-500 hover:text-gray-300 p-1"
                title="Log out"
              >
                <Lock className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>

        <RunningProfilesBar
          profiles={profiles}
          selectedId={selectedId}
          onOpenProfile={handleSelect}
          onStopProfile={handleStopProfile}
        />

        {/* Error banner */}
        {error && (
          <div className="px-4 py-2 bg-red-600/15 border-b border-red-600/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto overscroll-contain">
          {view === "empty" && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-gray-500 text-sm">Select a profile or create a new one</p>
              </div>
            </div>
          )}

          {view === "inventory" && (
            <InventoryTable
              profiles={profiles}
              onNewProfile={handleNew}
              onOpenProfile={handleSelect}
              onLaunchProfile={handleLaunchProfile}
              onStopProfile={handleStopProfile}
              onRefreshProfiles={refresh}
              onArchiveProfile={handleArchiveProfile}
              onRestoreProfile={handleRestoreProfile}
            />
          )}

          {view === "registration" && (
            <RegistrationLinksPlugin
              profiles={profiles}
              onOpenProfile={handleSelect}
            />
          )}

          {view === "research" && (
            <ResearchCenter />
          )}

          {view === "create" && (
            <ProfileForm
              profile={null}
              onSave={handleCreate}
              onCancel={() => setView("inventory")}
            />
          )}

          {view === "edit" && selected && (
            <ProfileForm
              profile={selected}
              onSave={handleUpdate}
              onDelete={handleDelete}
              onCancel={() => {
                setSelectedId(null);
                setView("inventory");
              }}
            />
          )}

          {view === "view" && selected && selected.status === "running" && (
            <ProfileViewer
              key={selected.id}
              profileId={selected.id}
              cdpUrl={selected.cdp_url}
              clipboardSync={selected.clipboard_sync}
              onDisconnect={handleVncDisconnect}
            />
          )}
        </div>
      </div>
    </div>
  );
}
