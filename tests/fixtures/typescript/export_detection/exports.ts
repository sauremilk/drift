// Explicitly exported function
export function processOrder(orderId: string): Promise<void> {
    console.log("processing", orderId);
}

// Default export
export default function handler(req: Request): Response {
    return new Response("ok");
}

// Exported arrow function
export const helper = (x: number): number => x * 2;

// Non-exported (module-private) function
function _internal(): void {
    console.log("internal");
}

// Public-named but not exported
function computeTotal(items: number[]): number {
    return items.reduce((a, b) => a + b, 0);
}

// Another non-exported arrow function
const formatter = (val: string): string => val.trim();
