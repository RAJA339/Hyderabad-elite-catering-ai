import { AdminShell } from "@/components/admin-shell";
export const metadata = { title: "Admin" };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
