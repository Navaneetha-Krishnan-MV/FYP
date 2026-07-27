import { useCallback, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { AddProjectModal } from '../components/AddProjectModal';

/** Shared by every routed page via `useOutletContext<AppOutletContext>()`. */
export interface AppOutletContext {
  /** Bumped whenever a project is ingested, so lists know to refetch. */
  dataVersion: number;
  openAddProject: () => void;
}

/**
 * Owns the chrome (nav + footer) and the globally reachable "Ingest Repository"
 * modal, so the header button works from any route.
 */
export function AppLayout() {
  const [isAddProjectOpen, setIsAddProjectOpen] = useState(false);
  const [dataVersion, setDataVersion] = useState(0);

  const openAddProject = useCallback(() => setIsAddProjectOpen(true), []);
  const closeAddProject = useCallback(() => setIsAddProjectOpen(false), []);
  const handleProjectCreated = useCallback(() => setDataVersion((v) => v + 1), []);

  const context: AppOutletContext = { dataVersion, openAddProject };

  return (
    <AppShell onOpenAddProject={openAddProject}>
      <Outlet context={context} />
      <AddProjectModal
        isOpen={isAddProjectOpen}
        onClose={closeAddProject}
        onSuccess={handleProjectCreated}
      />
    </AppShell>
  );
}
