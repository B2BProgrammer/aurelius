{{/* The service name: the Helm release name (conductor, librarian, ...). */}}
{{- define "agent.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* registry/repository:tag, e.g. mycompany.jfrog.io/aurelius-docker-dev/conductor:3f2a9c1 */}}
{{- define "agent.image" -}}
{{- $repo := .Values.image.repository | default (include "agent.name" .) -}}
{{- $tag := required "image.tag is required: the git SHA built by CI (--set image.tag=...)" .Values.image.tag -}}
{{- if .Values.image.registry -}}
{{ .Values.image.registry }}/{{ $repo }}:{{ $tag }}
{{- else -}}
{{ $repo }}:{{ $tag }}
{{- end -}}
{{- end -}}

{{- define "agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agent.name" . }}
app.kubernetes.io/part-of: aurelius
{{- end -}}

{{- define "agent.labels" -}}
{{ include "agent.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
