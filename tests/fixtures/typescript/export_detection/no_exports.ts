// No exports in this file — all functions are module-private

function privateHelper(): void {
    console.log("private");
}

function anotherHelper(x: number): number {
    return x + 1;
}

const compute = (a: number, b: number): number => a + b;
