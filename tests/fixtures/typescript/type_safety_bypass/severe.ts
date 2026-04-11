// Severe type safety bypasses (8+ bypasses)

// 1. as any
const data = fetchData() as any;

// 2. as any again
const response = JSON.parse(body) as any;

// 3. double cast (as unknown as SomeType)
const user = data as unknown as User;

// 4. non-null assertion
const el = document.querySelector(".btn")!;

// 5. non-null assertion
const parent = el.parentElement!;

// 6. @ts-ignore
// @ts-ignore
const x = undeclared + 1;

// 7. @ts-ignore
// @ts-ignore
console.log(missingModule.run());

// 8. @ts-expect-error
// @ts-expect-error
const y: number = "not a number";

interface User {
    id: string;
    name: string;
}
