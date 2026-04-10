import { useState, useEffect } from "react";

// Custom hook in a services/ directory (not hooks/) - HOOK_PLACEMENT_VIOLATION
export function useAuth() {
    const [user, setUser] = useState(null);

    useEffect(() => {
        checkAuth().then(setUser);
    }, []);

    return { user };
}
