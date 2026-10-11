import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ResizableTh from '../components/common/ResizableTh';

function renderTh(width: number, minWidth?: number) {
  render(
    <table>
      <thead>
        <tr>
          <ResizableTh width={width} minWidth={minWidth} onResize={() => {}}>
            Действия
          </ResizableTh>
        </tr>
      </thead>
    </table>,
  );
  return screen.getByText('Действия').closest('th')!;
}

describe('ResizableTh', () => {
  it('floors tiny stored widths at minWidth so columns never clip', () => {
    const th = renderTh(28, 150);
    // Chrome ignores min/max-width on fixed-layout cells and uses `width`
    // only — so the floor must land on `width` itself.
    expect(th.style.width).toBe('150px');
  });

  it('keeps healthy widths untouched', () => {
    const th = renderTh(200, 150);
    expect(th.style.width).toBe('200px');
  });
});
