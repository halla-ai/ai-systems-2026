```markdown
# Redis 연결 문제 Runbook

## 📌 Overview
Redis 서버와의 연결이 일정 시간 후 끊어지면서 `Connection pool exhausted` 오류가 발생하는 문제가 발견되었습니다. 이로 인해 애플리케이션에서 Redis에 대한 안정적인 연결이 불가능해지는 문제가 있었습니다.

## 🔍 Root Cause
이 문제의 근본 원인은 서버 방화벽 설정에서 유휴 연결(Idle Connection)을 감지하여 300초마다 끊기게 설정되어 있었기 때문입니다. 방화벽이 유휴 상태의 연결을 강제로 종료하면서 Redis 클라이언트는 연결을 제대로 유지할 수 없게 되었고, 최종적으로 `Connection pool exhausted` 오류를 유발했습니다.

## 🛠 Resolution Steps
이 문제를 해결하기 위해서는 Redis 클라이언트에 TCP Keepalive 기능을 활성화하고, 주기적으로 연결 상태를 확인할 수 있는 옵션을 설정해야 합니다. 아래는 `redis-py` Python 클라이언트를 사용하는 경우의 설정 단계입니다:

1. **Redis 클라이언트의 TCP Keepalive 활성화**
   - Redis 클라이언트를 초기화할 때, TCP Keepalive 옵션을 활성화합니다.
   - 예시:

   ```python
   import redis

   # Redis 클라이언트 초기화
   client = redis.StrictRedis(
       host='your_redis_server_host',
       port=6379,
       socket_keepalive=True  # TCP Keepalive 활성화
   )
   ```

2. **health_check_interval 옵션 추가**
   - 클라이언트 연결을 초기화할 때, health_check_interval 옵션을 설정하여 주기적으로 연결 상태를 확인합니다. 예를 들어, 60초마다 재확인을 하려면 다음과 같이 설정합니다:
   
   ```python
   import redis

   client = redis.StrictRedis(
       host='your_redis_server_host',
       port=6379,
       health_check_interval=60  # 60초마다 연결 상태 확인
   )
   ```

3. **방화벽 설정 검토 및 조정**
   - 방화벽의 유휴 연결 타임아웃 설정을 검토하여 설정값을 연장하거나, 필요한 경우 네트워크 팀에 요구사항을 전달합니다.

## ⚠️ Caveats
- TCP Keepalive를 활성화하면 일부 시스템 환경에서는 네트워크 대역폭 증가가 있을 수 있으므로 네트워크 부하를 감시해야 합니다.
- health_check_interval 설정을 너무 짧게 설정할 경우 불필요하게 많은 PING 명령어가 전송될 수 있으므로 적절한 주기를 설정하는 것이 중요합니다.
- redis-py 이외의 다른 클라이언트를 사용하는 경우에는 해당 클라이언트의 문서를 참조하여 유사한 설정을 적용하십시오.
- 이 문제와 해결 방안을 문서화하여 다른 팀원들에게 공유함으로써 동일한 문제가 반복되지 않도록 주의해야 합니다.
```
