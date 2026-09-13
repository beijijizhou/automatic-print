from dataclasses import replace
from pathlib import Path

from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.batch_analysis import analyze_batch
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.order_groups import order_key
from automatic_print.layout_engine.source_metadata import source_size


def source(tmp_path, order, size, w=180, h=260, piece=1, side=1):
    path = tmp_path/f'{order}-{piece}-T-Black-{size}-NO1-{side}.png'
    Image.new('RGBA', (w,h), 'blue').save(path, dpi=(25.4,25.4))
    return path


def settings(**kwargs):
    return replace(LayoutSettings(dpi=25.4, cutter_mode='dual', cutter_auto_knife=True,
        cutter_rotation_zone=True, number_images=False, margin_mm=0), **kwargs)


def test_batch_counts_garments_not_images_and_normalizes_xxl(tmp_path):
    paths = [source(tmp_path,'BSINGLE','XXL'),
             source(tmp_path,'BDOUBLE','3XL',side=1), source(tmp_path,'BDOUBLE','3XL',side=2),
             source(tmp_path,'BMULTI','S',piece=1), source(tmp_path,'BMULTI','M',piece=2)]
    stages=[]
    report=analyze_batch(paths,settings(),ready=stages.append)
    assert report['batch_type']=='混合批次'
    assert report['kinds']=={'单件单面':1,'单件双面':1,'多件订单':1}
    assert report['piece_count']==4
    assert report['image_count']==5
    assert report['double_pairs']==1
    assert report['single_sizes']=={'2XL':1}
    assert report['sizes']['3XL']==1
    assert stages[0]['stage']=='文件名分析'
    assert 'width_mm' not in stages[0]['orders'][0]['items'][0]['images'][0]
    assert 'width_mm' in stages[-1]['orders'][0]['items'][0]['images'][0]


def test_single_single_sizes_stay_together_with_aliases(tmp_path):
    paths=[source(tmp_path,f'B{i}',s) for i,s in enumerate(('XL','S','XXL','M','2XL','S','XL','M'))]
    planned=plan_layout(paths,settings(cutter_rotation_zone=False),None)[0]
    assert [source_size(p) for p,_ in planned]==['S','S','M','M','XL','XL','2XL','2XL']


def test_small_image_can_pair_with_large_size_without_breaking_a_double(tmp_path):
    large=source(tmp_path,'BLARGE','5XL',w=340,h=380)
    double=[source(tmp_path,'BDOUBLE','M',side=s) for s in (1,2)]
    small=source(tmp_path,'BCHEST','S',w=100,h=160)
    planned=plan_layout([large,*double,small],settings(cutter_rotation_zone=False),None)[0]
    lookup=dict(planned)
    assert lookup[large].y_px==lookup[small].y_px
    assert lookup[large].x_px!=lookup[small].x_px
    assert abs([p for p,_ in planned].index(double[0])-[p for p,_ in planned].index(double[1]))==1


def test_large_size_is_measured_and_slender_order_rotates(tmp_path):
    paths=[source(tmp_path,'BSLENDER','M',w=80,h=330),
           source(tmp_path,'BLARGE','4XL',w=310,h=200),
           source(tmp_path,'BCHEST','S',w=100,h=150)]
    stages=[]
    result=generate_layout(paths,tmp_path/'unused',settings(),preview_only=True,analysis_ready=stages.append)
    assert not (tmp_path/'unused').exists()
    assert [r['stage'] for r in stages]==['文件名分析','排版前分析','分区候选分析','排版结果']
    orders={o['order']:o for o in result['analysis']['orders']}
    assert orders['BSLENDER']['decision']=='旋转区'
    assert orders['BLARGE']['decision']=='常规区'
    assert orders['BCHEST']['companions']==['BLARGE']
    assert orders['BLARGE']['large_sizes']==['4XL']
    assert orders['BCHEST']['hints']==['小幅图']


def test_unfit_rotation_explains_why_whole_order_stays_normal(tmp_path):
    paths=[source(tmp_path,'BTALL','2XL',w=150,h=700),
           source(tmp_path,'BTALL','S',w=100,h=300,piece=2)]
    result=generate_layout(paths,tmp_path/'unused',settings(),preview_only=True)
    order=result['analysis']['orders'][0]
    assert not order['rotation_eligible']
    assert order['decision']=='常规区'
    assert '无法整体进入旋转区' in order['reason']


def test_unknown_and_orphan_back_are_not_declared_single_orders(tmp_path):
    path=source(tmp_path,'BORPHAN','M',side=2)
    unknown=tmp_path/'unknown.png'
    Image.new('RGBA',(80,100),'blue').save(unknown)
    report=analyze_batch([path,unknown],settings())
    assert report['kinds']=={'待核对归属':2}
    assert report['piece_count']==0
    assert report['single_sizes']=={}


def test_mixed_size_single_orders_validate_whole_output_pixels(tmp_path):
    paths=[source(tmp_path,f'B{i}',size,w=w,h=h) for i,(size,w,h) in enumerate((
        ('S',180,260),('5XL',340,380),('XL',80,330),('M',180,260),
        ('S',100,160),('M',180,260),('S',180,260),('2XL',180,260),
        ('XXL',180,260),('XL',180,260)))]
    result=generate_layout(paths,tmp_path/'out',settings())
    assert result['cut_corridor']['checked_images']==len(paths)
    assert result['cut_corridor']['pixel_verified']
    assert result['analysis']['single_sizes']['2XL']==2
    assert {p['sequence_number'] for p in result['placements']}==set(range(1,11))
    assert result['analysis']['image_count']==len(paths)
