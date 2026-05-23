pipeline {
    agent {
        kubernetes {
            namespace 'jenkins-agents'
            inheritFrom 'jenkins-agent'
            yaml '''
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: jenkins-agent
  imagePullSecrets:
  - name: harbor-credentials
  containers:
  - name: jenkins-agent
    image: harbor.rmwhs.space/devops/jenkins-agent:latest
    imagePullPolicy: Always
    command:
    - sleep
    args:
    - infinity
    tty: true
    env:
    - name: DOCKER_HOST
      value: tcp://localhost:2375
  - name: dind
    image: docker:24-dind
    securityContext:
      privileged: true
    env:
    - name: DOCKER_TLS_CERTDIR
      value: ""
'''
            defaultContainer 'jenkins-agent'
        }
    }

    environment {
        HARBOR_REGISTRY  = 'harbor.rmwhs.space'
        HARBOR_PROJECT   = 'apps'
        IMAGE_NAME       = 'ai-python-demo'
        IMAGE_TAG        = "${BUILD_NUMBER}"
        FULL_IMAGE       = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:${IMAGE_TAG}"
        LATEST_IMAGE     = "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${IMAGE_NAME}:latest"
        SONAR_PROJECT    = 'ai-python-demo'
        K8S_NAMESPACE    = 'ai-python-demo'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log --oneline -5'
            }
        }

        stage('SonarQube Scan') {
            steps {
                withSonarQubeEnv('SonarQube') {
                    sh '''
        sonar-scanner \
          -Dsonar.projectKey=${SONAR_PROJECT} \
          -Dsonar.projectName="AI Python Demo" \
          -Dsonar.sources=. \
          -Dsonar.exclusions=**/migrations/**,**/__pycache__/**,**/static/**,**/templates/**,**/tests/**
      '''
                }
            }
        }

        stage('Quality Gate') {
            steps {
                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
          docker build \
            -t ${FULL_IMAGE} \
            -t ${LATEST_IMAGE} \
            .
        '''
            }
        }

        stage('Trivy Image Scan') {
            steps {
                sh '''
          trivy image \
            --exit-code 0 \
            --severity CRITICAL \
            --no-progress \
            --format table \
            ${FULL_IMAGE}
        '''
            }
        }

        stage('Push to Harbor') {
            steps {
                withCredentials([usernamePassword(
          credentialsId: 'harbor-credentials',
          usernameVariable: 'HARBOR_USER',
          passwordVariable: 'HARBOR_PASS'
        )]) {
                    sh '''
            echo "${HARBOR_PASS}" | docker login ${HARBOR_REGISTRY} -u ${HARBOR_USER} --password-stdin
            docker push ${FULL_IMAGE}
            docker push ${LATEST_IMAGE}
          '''
        }
            }
        }

        stage('Update Image Tag') {
            steps {
                sh '''
          sed -i "s|harbor.rmwhs.space/apps/ai-python-demo:.*|harbor.rmwhs.space/apps/ai-python-demo:${IMAGE_TAG}|g" \
            k8s/deployment-with-fluent-bit.yaml
        '''
            }
        }

        stage('Deploy to Kubernetes') {
            steps {
                sh '''
          kubectl create namespace ${K8S_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
          kubectl apply -f k8s/postgres-init-configmap.yaml
          kubectl apply -f k8s/configmap.yaml
          kubectl apply -f k8s/fluent-bit-configmap.yaml
          kubectl apply -f k8s/postgres.yaml
          kubectl apply -f k8s/deployment-with-fluent-bit.yaml
          kubectl apply -f k8s/service.yaml
          kubectl apply -f k8s/ingress.yaml
          kubectl apply -f k8s/servicemonitor.yaml
          kubectl rollout status deployment/ai-python-demo -n ${K8S_NAMESPACE} --timeout=300s
        '''
            }
        }
    }

    post {
        success {
            echo "Deployed ${FULL_IMAGE} to ${K8S_NAMESPACE} successfully."
        }
        failure {
            echo 'Pipeline failed.'
        }
    }
}
