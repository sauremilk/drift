import React, { useEffect, useState } from "react";

// MISSING_DEPENDENCY_ARRAY: useEffect without dependency array
function DataFetcher() {
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchData().then(setData);
    });

    return <div>{data}</div>;
}
