// Dominant I-prefix convention: 10 with I-prefix, 2 without
interface IUser {
    id: string;
    name: string;
}

interface IProduct {
    sku: string;
    price: number;
}

interface IOrder {
    orderId: string;
    items: IProduct[];
}

interface IPayment {
    amount: number;
    currency: string;
}

interface IShipping {
    address: string;
    method: string;
}

interface IInvoice {
    total: number;
    date: string;
}

interface INotification {
    message: string;
    type: string;
}

interface ILogger {
    log(msg: string): void;
}

interface ICache {
    get(key: string): unknown;
    set(key: string, value: unknown): void;
}

interface IConfig {
    host: string;
    port: number;
}

// Outliers — NOT using I-prefix (should be flagged)
interface Repository {
    findAll(): unknown[];
}

interface Service {
    run(): void;
}
