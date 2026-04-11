// Clean TypeScript — no type safety bypasses
interface User {
    id: string;
    name: string;
}

function getUser(id: string): User | undefined {
    return { id, name: "Alice" };
}

const result: User | undefined = getUser("1");
if (result) {
    console.log(result.name);
}

type Status = "active" | "inactive";
const status: Status = "active";
