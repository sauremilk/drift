// Mixed generic parameter naming in one file
interface Mapper<T, TResult> {
    map(input: T): TResult;
}

function transform<K, InputType>(key: K, input: InputType): K {
    return key;
}

type Resolver<V, OutputValue> = (value: V) => OutputValue;
