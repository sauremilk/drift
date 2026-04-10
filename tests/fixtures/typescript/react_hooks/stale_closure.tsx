import React, { useEffect, useState } from "react";

// STALE_CLOSURE: empty deps array but references count in callback
function Counter() {
    const [count, setCount] = useState(0);

    useEffect(() => {
        const interval = setInterval(() => {
            setCount(count + 1);
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    return <div>{count}</div>;
}
