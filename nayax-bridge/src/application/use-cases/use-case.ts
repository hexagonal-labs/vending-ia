/**
 * Contrato comun de todos los casos de uso.
 *
 * Un caso de uso = una accion de negocio = una clase con un solo metodo.
 * Si te ves anadiendo un segundo metodo publico, es que hacen falta dos casos
 * de uso (principio de responsabilidad unica).
 */
export interface UseCase<TInput, TOutput> {
  execute(input: TInput): Promise<TOutput>;
}
