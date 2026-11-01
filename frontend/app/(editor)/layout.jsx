import AuthGuard from "../../components/layout/AuthGuard";

// Full-screen writing environment: no sidebar, same auth + theme as the rest.
export default function EditorGroupLayout({ children }) {
  return <AuthGuard>{children}</AuthGuard>;
}
