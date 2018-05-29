import pygame
import numpy as np
import time
import transforms3d.euler as euler

import reader
from transfer import *
from vistool import *
from skeleton import *
from smpl_np import SMPLModel

from OpenGL.GL import *
from OpenGL.GLU import *


class Viewer:
  def __init__(self, asf_joints, smpl_joints, motions):
    self.asf_joints = asf_joints
    self.smpl_joints = smpl_joints
    align_smpl_asf(asf_joints, smpl_joints)

    self.motions = motions
    self.frame = 0
    self.playing = False
    self.fps = 120

    self.rorate_dragging = False
    self.translate_dragging = False
    self.old_x = 0
    self.old_y = 0
    self.global_rx = 0
    self.global_ry = 0
    self.rotation_R = np.eye(3)
    self.speed_rx = np.pi / 90
    self.speed_ry = np.pi / 90
    self.speed_trans = 0.25
    self.speed_zoom = 0.5
    self.done = False
    self.default_translate = np.array([0, 0, -200], dtype=np.float32)
    self.translate = np.copy(self.default_translate)

    self.smpl_default_translate = np.array([-40, 0, 0], dtype=np.float32)
    self.smpl_translate = np.copy(np.array([-40, 0, 0], dtype=np.float32))

    pygame.init()
    self.screen_size = (1024, 768)
    self.screen = pygame.display.set_mode(self.screen_size, pygame.DOUBLEBUF | pygame.OPENGL)
    pygame.display.set_caption('AMC Parser - frame %d / %d' % (self.frame, len(self.motions)))
    self.clock = pygame.time.Clock()

    glClearColor(0, 0, 0, 0)
    glShadeModel(GL_SMOOTH)
    glMaterialfv(GL_FRONT, GL_SPECULAR, np.array([1, 1, 1, 1], dtype=np.float32))
    glMaterialfv(GL_FRONT, GL_SHININESS, np.array([100.0], dtype=np.float32))
    glMaterialfv(GL_FRONT, GL_AMBIENT, np.array([0.7, 0.7, 0.7, 0.7], dtype=np.float32))
    glEnable(GL_POINT_SMOOTH)

    glLightfv(GL_LIGHT0, GL_POSITION, np.array([1, 1, 1, 0], dtype=np.float32))
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHTING)
    glEnable(GL_DEPTH_TEST)
    gluPerspective(45, (self.screen_size[0]/self.screen_size[1]), 0.1, 500.0)

    glPointSize(10)
    glLineWidth(2.5)

  def process_event(self):
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        self.done = True
      elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_RETURN:
          self.translate = self.default_translate
          self.smpl_translate = self.smpl_default_translate
          self.global_rx = 0
          self.global_ry = 0
        elif event.key == pygame.K_SPACE:
          self.playing = not self.playing
      elif event.type == pygame.MOUSEBUTTONDOWN:
        if event.button == 1:
          self.rorate_dragging = True
        else:
          self.translate_dragging = True
        self.old_x, self.old_y = event.pos
      elif event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1:
          self.rorate_dragging = False
        else:
          self.translate_dragging = False
      elif event.type == pygame.MOUSEMOTION:
        if self.translate_dragging:
          # haven't figure out best way to implement this
          pass
        elif self.rorate_dragging:
          new_x, new_y = event.pos
          self.global_ry -= (new_x - self.old_x) / \
              self.screen_size[0] * np.pi
          self.global_rx -= (new_y - self.old_y) / \
              self.screen_size[1] * np.pi
          self.old_x, self.old_y = new_x, new_y
    pressed = pygame.key.get_pressed()
    if pressed[pygame.K_DOWN]:
      self.global_rx -= self.speed_rx
    if pressed[pygame.K_UP]:
      self. global_rx += self.speed_rx
    if pressed[pygame.K_LEFT]:
      self.global_ry += self.speed_ry
    if pressed[pygame.K_RIGHT]:
      self.global_ry -= self.speed_ry
    if pressed[pygame.K_a]:
      self.translate[0] -= self.speed_trans
    if pressed[pygame.K_d]:
      self.translate[0] += self.speed_trans
    if pressed[pygame.K_w]:
      self.translate[1] += self.speed_trans
    if pressed[pygame.K_s]:
      self.translate[1] -= self.speed_trans
    if pressed[pygame.K_q]:
      self.translate[2] += self.speed_zoom
    if pressed[pygame.K_e]:
      self.translate[2] -= self.speed_zoom
    if pressed[pygame.K_COMMA]:
      self.frame -= 1
      if self.frame >= len(self.motions):
        self.frame = 0
    if pressed[pygame.K_PERIOD]:
      self.frame += 1
      if self.frame < 0:
        self.frame = len(self.motions) - 1
    if pressed[pygame.K_KP8]:
      self.smpl_translate[1] += self.speed_trans
    if pressed[pygame.K_KP2]:
      self.smpl_translate[1] -= self.speed_trans
    if pressed[pygame.K_KP4]:
      self.smpl_translate[0] -= self.speed_trans
    if pressed[pygame.K_KP6]:
      self.smpl_translate[0] += self.speed_trans

    grx = euler.euler2mat(self.global_rx, 0, 0)
    gry = euler.euler2mat(0, self.global_ry, 0)
    self.rotation_R = grx.dot(gry)

  def set_asf_joints(self, asf_joints):
    self.asf_joints = asf_joints

  def set_smpl_joints(self, smpl_joints):
    self.smpl_joints = smpl_joints

  def set_motion(self, motions):
    self.motions = motions

  def draw(self):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glBegin(GL_POINTS)
    self.draw_joints(self.asf_joints)
    self.draw_joints(self.smpl_joints)
    glEnd()

    glBegin(GL_LINES)
    self.draw_bones(self.asf_joints)
    self.draw_bones(self.smpl_joints)
    glEnd()

  def draw_joints(self, joints):
    for j in joints.values():
      coord = np.array(np.squeeze(j.coordinate).dot(self.rotation_R)+self.translate, dtype=np.float32)
      glVertex3f(*coord)

  def draw_bones(self, joints):
    for j in joints.values():
      child = j
      parent = j.parent
      if parent is not None:
        coord_x = np.array(np.squeeze(child.coordinate).dot(self.rotation_R)+self.translate, dtype=np.float32)
        coord_y = np.array(np.squeeze(parent.coordinate).dot(self.rotation_R)+self.translate, dtype=np.float32)
        glVertex3f(*coord_x)
        glVertex3f(*coord_y)

  def update_motion(self):
    self.asf_joints['root'].set_motion(self.motions[self.frame])

    R, offset = map_R_asf_smpl(asf_joints)
    self.smpl_joints[0].coordinate = offset
    self.smpl_joints[0].set_motion_R(R)
    self.smpl_joints[0].update_coord()
    move_skeleton(self.smpl_joints, self.smpl_translate)

    if self.playing:
      self.frame += 1
      if self.frame >= len(self.motions):
        self.frame = 0

  def run(self):
    while not self.done:
      self.process_event()
      self.update_motion()
      self.draw()
      pygame.display.set_caption('AMC Parser - frame %d / %d' % (self.frame, len(self.motions)))
      pygame.display.flip()
      self.clock.tick(self.fps)
    pygame.quit()


if __name__ == '__main__':
  asf_joints = reader.parse_asf('./data/01/01.asf')
  asf_joints['root'].reset_pose()

  smpl = SMPLModel('./model.pkl')
  smpl_joints = setup_smpl_joints(smpl)

  motions = reader.parse_amc('./data/01/01_01.amc')

  v = Viewer(asf_joints, smpl_joints, motions)
  v.run()
