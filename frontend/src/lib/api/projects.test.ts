import { beforeEach, describe, expect, it, vi } from 'vitest';

const getWithMetadata = vi.fn();
const get = vi.fn();
const post = vi.fn();
const put = vi.fn();
const remove = vi.fn();

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    getWithMetadata: (...args: unknown[]) => getWithMetadata(...args),
    get: (...args: unknown[]) => get(...args),
    post: (...args: unknown[]) => post(...args),
    put: (...args: unknown[]) => put(...args),
    delete: (...args: unknown[]) => remove(...args),
  },
}));

import {
  createProjectApi,
  deleteProjectApi,
  fetchProjectsPageApi,
  getProjectByIdApi,
  updateProjectApi,
} from './projects';

describe('projects API', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getWithMetadata.mockResolvedValue({
      data: [],
      headers: new Headers({ 'X-Total-Count': '0' }),
    });
  });

  it('sends pagination and active filters to the existing projects endpoint', async () => {
    await fetchProjectsPageApi({ page: 2, limit: 15, status: 'Active', priority: 'High' });

    expect(getWithMetadata).toHaveBeenCalledWith(
      '/projects?page=2&limit=15&status=Active&priority=High',
    );
  });

  it('uses encoded resource URLs and the correct CRUD methods', async () => {
    get.mockResolvedValue({ id: 'project/1' });
    post.mockResolvedValue({ id: 'project-1' });
    put.mockResolvedValue({ id: 'project-1' });
    remove.mockResolvedValue({ message: 'deleted' });

    await getProjectByIdApi('project/1');
    await createProjectApi({ name: 'Migration' });
    await updateProjectApi('project/1', { status: 'Active' });
    await deleteProjectApi('project/1');

    expect(get).toHaveBeenCalledWith('/projects/project%2F1');
    expect(post).toHaveBeenCalledWith('/projects', { name: 'Migration' });
    expect(put).toHaveBeenCalledWith('/projects/project%2F1', { status: 'Active' });
    expect(remove).toHaveBeenCalledWith('/projects/project%2F1');
  });
});
