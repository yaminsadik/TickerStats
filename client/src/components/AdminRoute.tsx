import { Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useUserProfile } from "../hooks/useUserProfile";

interface AdminRouteProps {
  children: React.ReactNode;
}

export default function AdminRoute({ children }: AdminRouteProps) {
  const { loading, isAdmin } = useUserProfile();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!isAdmin) {
    return <Navigate to="/profile" replace />;
  }

  return <>{children}</>;
}
