# Multi-Secretary Implementation Plan

## Overview
Currently, the system has a single orchestrator and one secretary assistant. This document outlines the plan for implementing support for multiple secretary assistants, allowing users to choose their preferred secretary with different prompts and models.

## Current State
- Single orchestrator
- Single secretary assistant
- No user-secretary mapping

## Required Changes

### 1. Database Changes
- Add user-secretary mapping in the database
- Use existing `Assistant` model with `is_secretary` flag
- Create new model for user-secretary mapping

### 2. Orchestrator Changes
- Modify orchestrator to handle multiple secretary instances
- Implement secretary selection logic based on user preferences
- Consider two approaches for secretary instance management:
  1. Create separate secretary instances for each user
  2. Create shared secretary instances based on configuration

## Implementation Steps

### Phase 1: Database Updates
1. Review existing `Assistant` model
2. Verify `is_secretary` flag functionality
3. Create new model for user-secretary mapping
4. Create and test database migrations

### Phase 2: Orchestrator Updates
1. Modify orchestrator to support multiple secretaries
2. Implement secretary selection logic
3. Update message routing based on user-secretary mapping
4. Add secretary instance management

### Phase 3: Testing
1. Unit tests for new models and logic
2. Integration tests for secretary selection
3. Performance testing for different secretary instance management approaches

## Technical Considerations

### Secretary Instance Management
Two possible approaches:

1. **Per-User Secretary Instances**
   - Pros:
     - Complete isolation between users
     - Independent context management
   - Cons:
     - Higher memory usage
     - More complex instance management

2. **Shared Secretary Instances**
   - Pros:
     - Lower resource usage
     - Simpler instance management
   - Cons:
     - Need to handle context separation within secretary
     - Potential for context mixing

## Detailed Implementation Plan

### Phase 1: Database Changes

1. **Create User-Secretary Link Model**:
```python
class UserSecretaryLink(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    secretary_id: UUID = Field(foreign_key="assistant.id")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

2. **REST API Updates**:
   - Add endpoints for:
     - Getting available secretaries list
     - Setting secretary for user
     - Getting user's current secretary

### Phase 2: Orchestrator Updates

1. **AssistantFactory Modifications**:
   - Add method for getting secretary by user_id
   - Implement secretary instance caching
   - Add cleanup mechanism for unused instances

2. **Orchestrator Changes**:
   - Add user_id extraction from incoming messages
   - Implement secretary selection for user
   - Add conversation context management per user

### Phase 3: Context Management

1. **Conversation Context Updates**:
   - Add user_id to context
   - Implement context isolation for different users
   - Add mechanism for old context cleanup

2. **Redis Updates**:
   - Modify context storage keys to include user_id
   - Add TTL for contexts

### Phase 4: Testing

1. **New Tests**:
   - User-secretary link tests
   - Context isolation tests
   - Secretary switching tests
   - Multi-user performance tests

2. **Integration Tests**:
   - Inter-service interaction tests
   - Real user scenario tests

### Phase 5: Documentation and Monitoring

1. **Documentation**:
   - Update API documentation
   - Add new data model descriptions
   - Update deployment instructions

2. **Monitoring**:
   - Add secretary usage metrics
   - System load monitoring
   - Error and issue tracking

## Questions to Resolve
1. Which secretary instance management approach to use?
2. How to handle secretary context separation?
3. Should we implement secretary switching for users?
4. How to handle secretary updates and migrations?
5. How long to store conversation context for each user?
6. How to handle inactive secretary situations?
7. How to handle existing user migration to the new system?

## Progress Tracking
- [x] Database model design
- [x] Database migrations
- [x] REST API endpoints implementation
- [ ] Orchestrator modifications
- [ ] Secretary selection logic
- [ ] Instance management implementation
- [ ] Testing
- [ ] Documentation updates

## Completed Work
1. Created `UserSecretaryLink` model with fields:
   - `id`: UUID (primary key)
   - `user_id`: int (foreign key to TelegramUser)
   - `secretary_id`: UUID (foreign key to Assistant)
   - `is_active`: bool
   - `created_at`: datetime
   - `updated_at`: datetime

2. Added relationships:
   - In `TelegramUser`: `secretary_links: List["UserSecretaryLink"]`
   - In `Assistant`: `user_links: List["UserSecretaryLink"]`

3. Created and applied initial migration with all tables

4. Fixed migration command in manage.py to use correct command name

5. Implemented REST API endpoints:
   - GET /api/secretaries/ - получение списка доступных секретарей
   - GET /api/users/{user_id}/secretary - получение текущего секретаря пользователя
   - POST /api/users/{user_id}/secretary/{secretary_id} - установка секретаря для пользователя

## Next Steps
1. Modify orchestrator to:
   - Handle multiple secretary instances
   - Select secretary based on user preferences
   - Manage secretary instances efficiently

2. Implement context management:
   - Add user_id to context
   - Ensure context isolation
   - Add cleanup mechanism

3. Add comprehensive testing:
   - Unit tests for new models and API endpoints
   - Integration tests for secretary selection
   - Performance tests

## Notes
- Keep changes minimal and focused
- Maintain backward compatibility
- Ensure proper error handling
- Consider performance implications 