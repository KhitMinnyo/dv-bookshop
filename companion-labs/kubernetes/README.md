# Kubernetes Security Companion Lab

This directory is a self-contained manifest comparison. `vulnerable.yaml`
shows common unsafe defaults and `hardened.yaml` shows a constrained local
variant. The manifests do not reference DV-Bookshop images, databases, or
namespaces. The Secret values are dummy examples and are not credentials.

## Exact Scope

Use only a disposable `kind` cluster or a disposable Minikube profile. Never
apply these files to a shared, production, or cloud cluster. The commands below
are instructions for an operator and have not been run by this lab. An Ingress
controller is optional; without one, the Ingress object is still useful for
inspection but has no traffic endpoint.

## Setup With kind

```sh
kind create cluster --name companion-k8s
kubectl create namespace companion-lab
kubectl apply -n companion-lab -f vulnerable.yaml
kubectl get all,sa,role,rolebinding,networkpolicy,secret,ingress -n companion-lab
```

To compare the hardened variant, reset the namespace first or use a second
disposable namespace:

```sh
kubectl delete namespace companion-lab
kubectl wait --for=delete namespace/companion-lab --timeout=60s
kubectl create namespace companion-lab
kubectl apply -n companion-lab -f hardened.yaml
```

## Setup With Minikube

```sh
minikube start -p companion-k8s
kubectl create namespace companion-lab
kubectl apply -n companion-lab -f hardened.yaml
```

The manifests use the image `nginx:1.27-alpine`; a local cluster may need
network access to pull it. No application data is mounted and no external
service is contacted by the lab itself.

## Exercises

1. Compare `automountServiceAccountToken`, `runAsNonRoot`, capabilities,
   filesystem mutability, and the two RBAC scopes.
2. Inspect the mounted token behavior in each Deployment. Explain why a
   service account token should not be available when the workload does not
   call the Kubernetes API. Do not extract or use a token outside the local
   disposable pod.
3. Use `kubectl auth can-i --as=system:serviceaccount:companion-lab:lab-vulnerable --list -n companion-lab` and compare it with the hardened account. The
   vulnerable RoleBinding is intentionally broad within its namespace.
4. Add a narrowly scoped read-only Role for one named ConfigMap, then explain
   why a ClusterRole is unnecessary.
5. Inspect the NetworkPolicies. Explain what traffic is denied by default and
   why DNS is the only permitted egress in the hardened policy.
6. Review the Secret. Explain why base64 is encoding rather than encryption,
   then replace the dummy value through a local secret-management workflow
   without committing a real value.
7. If an Ingress controller is installed in the disposable cluster, add a
   local hosts entry only for `bookshop.test` and test the hardened route. Do
   not publish the route or use a real hostname.

Useful inspection commands:

```sh
kubectl describe deployment -n companion-lab lab-hardened
kubectl get role,rolebinding,networkpolicy -n companion-lab -o yaml
kubectl auth can-i get secrets --as=system:serviceaccount:companion-lab:lab-hardened -n companion-lab
```

## Cleanup

```sh
kubectl delete namespace companion-lab --ignore-not-found
kind delete cluster --name companion-k8s
minikube delete -p companion-k8s
```

Run only the cleanup command for the cluster tool you used. The manifests do
not create cloud resources, persistent volumes, or real secrets.
