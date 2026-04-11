// Interface extending another
interface BaseEntity {
  id: string;
  createdAt: Date;
}

interface UserEntity extends BaseEntity {
  name: string;
  email: string;
  getDisplayName(): string;
}

// Interface with generics
interface Repository<T extends BaseEntity> {
  findById(id: string): Promise<T | null>;
  save(entity: T): Promise<T>;
  delete(id: string): Promise<void>;
}

// Interface with index signature and methods
interface EventMap {
  [key: string]: (...args: any[]) => void;
  on(event: string, handler: Function): void;
  off(event: string, handler: Function): void;
}
