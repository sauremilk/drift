import React, { useEffect } from "react";

// Clean effect: no dependency issues
function PageTitle() {
    useEffect(() => {
        document.title = "Hello";
    }, []);

    return <div>Hello</div>;
}
