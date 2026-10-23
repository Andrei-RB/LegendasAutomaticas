import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { createMemoryRouter, type RouteObject } from "react-router";
import { RouterProvider } from "react-router/dom";

export function criarClienteTeste(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

export function envolver(cliente: QueryClient) {
  return function Envoltorio({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={cliente}>{children}</QueryClientProvider>;
  };
}

export function montarRotas(rotas: RouteObject[], inicial: string, cliente = criarClienteTeste()) {
  const router = createMemoryRouter(rotas, { initialEntries: [inicial] });
  const Envoltorio = envolver(cliente);
  const resultado = render(
    <Envoltorio>
      <RouterProvider router={router} />
    </Envoltorio>,
  );
  return { router, cliente, ...resultado };
}
