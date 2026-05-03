import { useMutation } from "@tanstack/react-query";
import {
  subscriptionApi,
  type CheckoutItem,
  type CreateCheckoutSessionOptions,
} from "../api/subscriptionApi";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";

export function useSubscriptionMutations() {
  const { authenticatedFetch } = useAuthenticatedFetch();

  const checkoutMutation = useMutation({
    mutationFn: ({
      item,
      options,
    }: {
      item: CheckoutItem;
      options?: CreateCheckoutSessionOptions;
    }) => subscriptionApi.createCheckoutSession(authenticatedFetch, item, options),
    onSuccess: (data) => {
      // Redirect to Stripe Checkout
      if (data.url) {
        window.location.href = data.url;
      }
    },
  });

  const portalMutation = useMutation({
    mutationFn: () => subscriptionApi.createPortalSession(authenticatedFetch),
    onSuccess: (data) => {
      // Redirect to Stripe Customer Portal
      window.location.href = data.url;
    },
  });

  return {
    createCheckout: (
      item: CheckoutItem,
      options?: CreateCheckoutSessionOptions,
    ) => checkoutMutation.mutate({ item, options }),
    isCreatingCheckout: checkoutMutation.isPending,
    checkoutError:
      checkoutMutation.error instanceof Error
        ? checkoutMutation.error.message
        : checkoutMutation.error
          ? String(checkoutMutation.error)
          : null,
    createPortal: portalMutation.mutate,
    isCreatingPortal: portalMutation.isPending,
    portalError:
      portalMutation.error instanceof Error
        ? portalMutation.error.message
        : portalMutation.error
          ? String(portalMutation.error)
          : null,
  };
}
