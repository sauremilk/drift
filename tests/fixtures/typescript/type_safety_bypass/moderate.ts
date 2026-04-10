// Moderate type safety bypasses (3 bypasses)
interface Config {
    host: string;
    port: number;
}

// 1. as any cast
const config = JSON.parse(rawData) as any;

// 2. non-null assertion
const element = document.getElementById("root")!;

// 3. @ts-ignore
// @ts-ignore
const broken = undeclaredVar + 1;

// Clean code below (no bypasses)
function processConfig(cfg: Config): void {
    console.log(cfg.host, cfg.port);
}
