// Basic interface with method signatures
interface UserService {
  getUser(id: string): Promise<User>;
  updateUser(id: string, data: Partial<User>): Promise<void>;
}

// Type alias
type UserId = string;

// Interface with optional members
interface Config {
  host: string;
  port?: number;
  debug?: boolean;
}

// Type alias for union
type Result<T> = { ok: true; value: T } | { ok: false; error: string };
