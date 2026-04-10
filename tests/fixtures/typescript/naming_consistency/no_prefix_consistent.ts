// No I-prefix convention — all interfaces without I-prefix (consistent)
interface User {
    id: string;
    name: string;
}

interface Product {
    sku: string;
    price: number;
}

interface Order {
    orderId: string;
}

interface Config {
    host: string;
}
