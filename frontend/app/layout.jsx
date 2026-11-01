import "../styles/globals.css";
import { AuthProvider } from "../context/AuthContext";

export const metadata = {
  title: "IntelliTwin",
  description: "An AI Powered Intelligent Workspace",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="twin-canvas-bg min-h-screen">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
