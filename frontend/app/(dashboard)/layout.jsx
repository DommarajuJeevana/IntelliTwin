import Sidebar from "../../components/layout/Sidebar";
import MobileNav from "../../components/layout/MobileNav";
import AuthGuard from "../../components/layout/AuthGuard";
import NotificationListener from "../../components/layout/NotificationListener";

export default function DashboardGroupLayout({ children }) {
  return (
    <AuthGuard>
      <NotificationListener />

      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-ink-800 focus:px-4 focus:py-2 focus:text-sm focus:text-text"
      >
        Skip to content
      </a>

      <div className="flex min-h-screen flex-col lg:flex-row">
        <MobileNav />
        <Sidebar />

        <main id="main-content" className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
